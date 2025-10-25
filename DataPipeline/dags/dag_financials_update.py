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
from airflow.models import DAG
from airflow.operators.python import PythonOperator
from airflow.models.param import Param
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import func

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

logger = configure_kst_logger(__name__)

# ---------------------------------------------
# DAG 기본 설정
# ---------------------------------------------
default_args = {
    'owner': 'tradesmart_ai',
    'retries': 1,
    'retry_delay': pendulum.duration(minutes=10),
}


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

                # 기존 로직과 동일한 파싱/계산/저장 처리
                parser = _FinancialDataParser()
                financial_df = parser.parse(financials_raw, shares_raw or [])
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
                    analysis_date=today,
                    eps_growth_yoy=result.get('eps_growth_yoy'),
                    eps_annual_growth_avg=result.get('eps_annual_growth_avg'),
                    financial_grade=result.get('financial_grade')
                )

                upsert_stmt = stmt.on_conflict_do_update(
                    index_elements=['stock_code', 'analysis_date'],
                    set_={
                        'eps_growth_yoy': stmt.excluded.eps_growth_yoy,
                        'eps_annual_growth_avg': stmt.excluded.eps_annual_growth_avg,
                        'financial_grade': stmt.excluded.financial_grade,
                    }
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


# ---------------------------------------------
# DAG 정의
# ---------------------------------------------
with DAG(
    dag_id='dag_financials_update',
    default_args=default_args,
    description='[주간] 재무 분석 업데이트 - DART API 기반 EPS 성장률 및 재무 등급 판정',
    schedule_interval='0 2 * * 6',  # 매주 토요일 오전 2시 (KST 기준, UTC로 자동 변환됨)
    start_date=pendulum.datetime(2025, 1, 1, tz='Asia/Seoul'),
    catchup=False,
    tags=['Analysis', 'Financials', 'Weekly', 'LIVE'],
    params={
        "test_stock_codes": Param(
            type=["null", "string"],
            default="",
            title="[테스트용] 특정 종목 대상 실행",
            description="쉼표(,)로 구분된 종목 코드를 제공하면, 해당 종목들만 대상으로 분석합니다."
        ),
        "stock_limit": Param(
            type="integer",
            default=0,
            title="종목 수 제한 (0=제한 없음)",
            description="테스트 목적으로 처리할 종목 수를 제한합니다. 0 또는 음수이면 전체 종목을 처리합니다."
        ),
        "force_update_map": Param(
            type="boolean",
            default=False,
            title="DART 고유번호 맵 강제 업데이트",
            description="True로 설정 시, 캐시를 무시하고 DART API에서 고유번호 맵을 새로 다운로드합니다."
        ),
    },
    doc_md="""
    ## DAG: 재무 분석 업데이트 (dag_financials_update)
    
    ### 목적
    - 주간 단위로 모든 관리 대상 종목의 재무 데이터를 DART API로부터 수집
    - EPS 성장률 및 재무 등급을 분석하여 `financial_analysis_results` 테이블에 저장
    - `dag_daily_batch`의 부담을 줄이고 재무 분석을 독립적으로 관리
    
    ### 실행 전략
    1. **데이터 소스**: DART API (실시간 재무 데이터)
    2. **분석 대상**: `live.stocks`에서 `is_active=True`인 종목
    3. **저장 위치**: `live.financial_analysis_results` 테이블
    4. **Rate Limiting**: 종목당 0.5초 대기 (DART API 제한 준수)
    
    ### 파라미터
    - `stock_limit` (기본값: 0): 테스트 시 처리할 종목 수 제한
    
    ### 의존성
    - `src.analysis.financial_engine`: 재무 분석 핵심 로직
    - `src.master_data_manager`: 활성 종목 조회
    - `src.dart_api.client`: DART API 클라이언트
    """,
) as dag:
    
    analyze_and_store_financials_task = PythonOperator(
        task_id='analyze_and_store_financials',
        python_callable=_analyze_and_store_financials,
        doc_md="""
        #### Task: 재무 분석 및 저장
        - DART API로 재무 데이터 수집
        - EPS 계산 및 재무 등급 판정
        - `financial_analysis_results` 테이블에 UPSERT
        """,
    )
    
    # 이 DAG는 단일 Task로 구성
    analyze_and_store_financials_task

