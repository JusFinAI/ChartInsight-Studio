"""
DAG: 재무 분석 업데이트 (dag_financials_update)

주간 단위로 모든 관리 대상 종목의 재무 데이터를 DART API로부터 수집하고,
EPS 성장률 및 재무 등급을 분석하여 financial_analysis_results 테이블에 저장합니다.

Schedule: 매주 토요일 오전 2시
Strategy: 
    - DB의 live.stocks에서 is_active=True인 종목들을 대상으로 분석
    - DART API Rate Limiting (0.5초 대기)
    - 개별 종목 실패가 전체 DAG 실패로 이어지지 않도록 예외 처리
"""

import logging
import time
from datetime import date, datetime

import pendulum
from airflow.models import DAG, Variable
from airflow.operators.python import PythonOperator
from airflow.exceptions import AirflowException
from airflow.models.param import Param
from sqlalchemy import text, func, and_
from sqlalchemy.dialects.postgresql import insert

from src.database import SessionLocal, FinancialAnalysisResult, Stock
from src.master_data_manager import get_managed_stocks_from_db
from src.analysis.financial_engine import (
    fetch_live_financial_data,
    _FinancialDataParser,
    _EpsCalculator,
    _FinancialGradeAnalyzer
)
from src.dart_api.dart_corp_map import get_corp_code_map, get_corp_code
from src.utils.logging_kst import configure_kst_logger

logger = logging.getLogger(__name__)

DEFAULT_ARGS = {
    'owner': 'tradesmart_ai',
    'retries': 1,
    'retry_delay': pendulum.duration(minutes=10),
}

logger = configure_kst_logger(__name__)

# ---------------------------------------------
# LIVE 모드: 기존 검증된 재무 분석 함수
# ---------------------------------------------
def _analyze_and_store_financials(**kwargs):
    """재무 분석 및 저장 Task"""
    params = kwargs.get('params', {})
    test_stock_codes_param = params.get('test_stock_codes', "")
    stock_limit = params.get('stock_limit', 0)

    db = SessionLocal()
    try:
        active_stocks = []
        if test_stock_codes_param:
            codes_to_process = []
            if isinstance(test_stock_codes_param, str):
                codes_to_process = [c.strip() for c in test_stock_codes_param.split(',') if c.strip()]
            elif isinstance(test_stock_codes_param, (list, tuple)):
                codes_to_process = [str(c).strip() for c in test_stock_codes_param if str(c).strip()]

            logger.info(f"test_stock_codes 파라미터로 실행 대상을 한정합니다: {len(codes_to_process)}개")
            if codes_to_process:
                existing = db.query(Stock.stock_code).filter(Stock.stock_code.in_(codes_to_process)).all()
                existing_set = {code for code, in existing}
                active_stocks = [c for c in codes_to_process if c in existing_set]
        else:
            active_stocks = get_managed_stocks_from_db(db)

        if not active_stocks:
            logger.warning("처리할 대상 종목이 없습니다. Task를 종료합니다.")
            return

        if not test_stock_codes_param and stock_limit > 0:
            active_stocks = active_stocks[:stock_limit]

        corp_map_df = get_corp_code_map(force_update=params.get('force_update_map', False))
        today = date.today()
        success_count, fail_count, skip_count = 0, 0, 0

        for idx, stock_code in enumerate(active_stocks, 1):
            logger.info(f"[{idx}/{len(active_stocks)}] {stock_code} 재무 분석 시작...")
            try:
                last_analysis_date = db.query(func.max(FinancialAnalysisResult.analysis_date)).filter(
                    FinancialAnalysisResult.stock_code == stock_code
                ).scalar()

                corp_code = get_corp_code(stock_code, corp_map_df)
                if not corp_code:
                    logger.warning(f"[{stock_code}] DART 고유번호 조회 실패, 건너뜀")
                    skip_count += 1
                    continue

                financials_raw, shares_raw = fetch_live_financial_data(corp_code, last_analysis_date)
                if not financials_raw:
                    logger.warning(f"[{stock_code}/{corp_code}] 신규 재무 데이터 없음, 건너뜀")
                    skip_count += 1
                    continue

                # ✅ parse()가 이제 (df, report_date) 튜플 반환
                parser = _FinancialDataParser()
                financial_df, report_date = parser.parse(financials_raw, shares_raw or [])
                
                # ✅ analysis_date 설정: rcept_no 날짜 우선, 없으면 오늘
                if report_date:
                    analysis_date = report_date
                    logger.info(f"[{stock_code}] 보고서 제출일: {analysis_date}")
                else:
                    analysis_date = today
                    logger.warning(f"[{stock_code}] rcept_no 추출 실패, 오늘 날짜 사용: {analysis_date}")
                
                # debug: show parsed DataFrame head and unique year-quarter combos
                try:
                    logger.info(f"[{stock_code}] parsed financial_df rows: {len(financial_df)}")
                    logger.info(f"[{stock_code}] financial_df.head():\n{financial_df.head().to_string()}" )
                    yq = financial_df[['year', 'quarter']].drop_duplicates().sort_values(['year', 'quarter'])
                    logger.info(f"[{stock_code}] year-quarter sample:\n{yq.to_string()}" )
                except Exception as e:
                    logger.debug(f"[{stock_code}] parsed DataFrame logging failed: {e}")

                if financial_df.empty:
                    logger.warning(f"[{stock_code}] 파싱 결과 비어있음, 건너뜀")
                    skip_count += 1
                    continue

                # 1단계: DART shares_raw에서 주식총수 추출 (istc_totqy 필드 사용)
                current_list_count = 0
                if shares_raw:
                    for item in reversed(shares_raw):
                        if item.get('se') == '보통주':
                            istc_totqy = item.get('istc_totqy', '0')  # DART API 필드명
                            try:
                                current_list_count = int(str(istc_totqy).replace(',', ''))
                                if current_list_count > 0:
                                    logger.info(f"[{stock_code}] DART 주식총수 사용: {current_list_count:,}")
                                    break
                            except (ValueError, TypeError):
                                continue

                # 2단계: DART에서 주식총수를 얻지 못한 경우, DB Stock.list_count 사용 (Kiwoom 최신 데이터)
                if current_list_count <= 0:
                    try:
                        stock_info = db.query(Stock).filter(Stock.stock_code == stock_code).first()
                        if stock_info and getattr(stock_info, 'list_count', None):
                            current_list_count = int(stock_info.list_count)
                            logger.info(f"[{stock_code}] DART 주식총수 없음, DB Stock.list_count 사용: {current_list_count:,}")
                        else:
                            logger.warning(f"[{stock_code}] 발행주식수 정보 없음 (DART & DB 모두), 건너뜀")
                            skip_count += 1
                            continue
                    except Exception as e:
                        logger.warning(f"[{stock_code}] DB 주식수 조회 중 오류: {e}, 건너뜀")
                        skip_count += 1
                        continue

                calculator = _EpsCalculator()
                eps_df = calculator.calculate(financial_df, current_list_count)

                if eps_df is None or eps_df.empty:
                    logger.warning(f"[{stock_code}] EPS 계산 실패, 건너뜀")
                    skip_count += 1
                    continue

                analyzer = _FinancialGradeAnalyzer()
                result = analyzer.analyze(eps_df)

                stmt = insert(FinancialAnalysisResult).values(
                    stock_code=stock_code,
                    analysis_date=analysis_date,  # ✅ rcept_no 기반 날짜 사용
                    eps_growth_yoy=result.get('eps_growth_yoy'),
                    eps_annual_growth_avg=result.get('eps_annual_growth_avg'),
                    financial_grade=result.get('financial_grade')
                )

                # ✅ Phase 2: 데이터歷史 보존 - 중복 저장 방지
                upsert_stmt = stmt.on_conflict_do_nothing(
                    index_elements=['stock_code', 'analysis_date']
                )

                db.execute(upsert_stmt)
                success_count += 1

                logger.info(
                    f"[{stock_code}] 재무 분석 완료 - 등급: {result.get('financial_grade')}, "
                    f"YoY: {result.get('eps_growth_yoy')}%, 연평균: {result.get('eps_annual_growth_avg')}%"
                )

            except Exception as e:
                logger.error(f"[{stock_code}] 재무 분석 중 오류 발생: {e}", exc_info=True)
                fail_count += 1
                continue

        db.commit()
        logger.info(f"재무 분석 완료 - 성공: {success_count}, 실패: {fail_count}, 건너뜀: {skip_count}")

    except Exception as e:
        db.rollback()
        logger.error(f"재무 분석 Task 전체 오류: {e}", exc_info=True)
        raise
    finally:
        db.close()


def _run_financials_update(**kwargs):
    params = kwargs.get('params', {})
    execution_mode = params.get('execution_mode', 'LIVE')
    logger.info(f"재무 분석 업데이트 시작: mode={execution_mode}")

    if execution_mode == 'SIMULATION':
        # --- SIMULATION 모드: 재무 데이터 스냅샷 준비 (Raw SQL, 보안 강화 버전) ---
        target_datetime_str = params.get('target_datetime')
        if not target_datetime_str:
            raise AirflowException("SIMULATION 모드에서는 'target_datetime' 파라미터가 필수입니다.")

        try:
            exec_dt = datetime.strptime(target_datetime_str, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            raise AirflowException("target_datetime 형식이 'YYYY-MM-DD HH:MM:SS'가 아닙니다.")

        db = SessionLocal()
        try:
            logger.info("SIMULATION 스냅샷에 재무 분석 데이터 포함을 시작합니다 (Raw SQL, 보안 강화 버전).")
            db.execute(text("TRUNCATE TABLE simulation.financial_analysis_results"))

            # 1. 대상 종목 리스트 및 SQL 파라미터 준비
            stock_codes_param = params.get('test_stock_codes', '') or ''
            stock_codes_list = [code.strip() for code in stock_codes_param.split(',') if code.strip()]
            sql_params = {'exec_date': exec_dt.date()}

            # 2. 종목 리스트 존재 여부에 따라 SQL 쿼리 분기 (SQL Injection 방지)
            if stock_codes_list:
                logger.info(f"지정된 {len(stock_codes_list)}개 종목 대상으로 재무 스냅샷 생성.")
                sql_params['stock_codes'] = stock_codes_list  # ANY()를 위해 리스트로 전달
                sql_query = """
                    INSERT INTO simulation.financial_analysis_results (
                        stock_code, analysis_date, eps_growth_yoy, eps_annual_growth_avg, financial_grade, created_at
                    )
                    SELECT
                        lfar.stock_code, lfar.analysis_date, lfar.eps_growth_yoy, lfar.eps_annual_growth_avg, lfar.financial_grade, lfar.created_at
                    FROM
                        live.financial_analysis_results AS lfar
                    INNER JOIN (
                        SELECT
                            stock_code,
                            MAX(analysis_date) AS max_date
                        FROM
                            live.financial_analysis_results
                        WHERE
                            analysis_date <= :exec_date
                            AND stock_code = ANY(:stock_codes) -- PostgreSQL 호환성을 위해 ANY() 사용
                        GROUP BY
                            stock_code
                    ) AS sub ON lfar.stock_code = sub.stock_code AND lfar.analysis_date = sub.max_date
                """
            else:
                logger.info("모든 종목 대상으로 재무 스냅샷 생성.")
                sql_query = """
                    INSERT INTO simulation.financial_analysis_results (
                        stock_code, analysis_date, eps_growth_yoy, eps_annual_growth_avg, financial_grade, created_at
                    )
                    SELECT
                        lfar.stock_code, lfar.analysis_date, lfar.eps_growth_yoy, lfar.eps_annual_growth_avg, lfar.financial_grade, lfar.created_at
                    FROM
                        live.financial_analysis_results AS lfar
                    INNER JOIN (
                        SELECT
                            stock_code,
                            MAX(analysis_date) AS max_date
                        FROM
                            live.financial_analysis_results
                        WHERE
                            analysis_date <= :exec_date
                        GROUP BY
                            stock_code
                    ) AS sub ON lfar.stock_code = sub.stock_code AND lfar.analysis_date = sub.max_date
                """

            # 3. 쿼리 실행
            result = db.execute(text(sql_query), sql_params)
            db.commit()

            logger.info(f"✅ 재무 분석 데이터 스냅샷 복제 완료: {result.rowcount} 행")

        except Exception as e:
            logger.error(f"Raw SQL을 이용한 재무 스냅샷 생성 중 오류: {e}", exc_info=True)
            db.rollback()
            raise
        finally:
            db.close()

    else:
        # --- LIVE 모드: 기존 검증된 로직 실행 ---
        logger.info("LIVE 모드 재무 분석 실행")
        _analyze_and_store_financials(**kwargs)


with DAG(
    dag_id='dag_financials_update',
    default_args=DEFAULT_ARGS,
    schedule_interval='0 2 * * 6',
    #start_date=pendulum.datetime(2025, 1, 1, tz='Asia/Seoul'),
    start_date=pendulum.now('Asia/Seoul').subtract(hours=1),
    catchup=False,
    tags=['Analysis', 'Financials', 'Weekly'],
    params={
        "execution_mode": Param(default="LIVE", type="string", enum=["LIVE", "SIMULATION"]),
        "target_datetime": Param(default="", type=["null", "string"], description="YYYY-MM-DD HH:MM:SS"),
        "test_stock_codes": Param(default="", type=["null", "string"], description="쉼표구분 종목코드")
    },
) as dag:
    run_financials_update_task = PythonOperator(
        task_id='run_financials_update',
        python_callable=_run_financials_update,
    )

