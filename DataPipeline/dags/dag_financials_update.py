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
    """재무 분석 및 저장 Task
    
    모든 활성 종목에 대해:
    1. DART API로 재무 데이터 수집
    2. EPS 계산 및 재무 등급 판정
    3. financial_analysis_results 테이블에 UPSERT
    """
    # =================================================================
    # DEBUG: 실행 시점의 환경 변수 확인
    # =================================================================
    import os
    print(f"DEBUG PRINT: Task is using DART_API_KEY starting with: {os.getenv('DART_API_KEY')[:4] if os.getenv('DART_API_KEY') else 'None'}")
        
    params = kwargs.get('params', {})
    stock_codes_str = params.get('stock_codes', "")
    stock_limit = params.get('stock_limit', 0)

    db = SessionLocal()
    try:
        # --- START: 디버깅 코드 v2 (print 사용) ---
        try:
            print("--- DEBUGGING: INSIDE _analyze_and_store_financials ---")
            stock_count = db.query(Stock).count()
            print(f"DEBUG PRINT: live.stocks table count is: {stock_count}")
        except Exception as e:
            print(f"DEBUG PRINT: An exception occurred during DB query: {e}")
        # --- END: 디버깅 코드 v2 ---

        # 1. 활성 종목 리스트 조회 / 또는 파라미터로 전달된 특정 종목 사용
        active_stocks = []
        if stock_codes_str:
            # 파라미터로 쉼표로 구분된 종목 코드가 제공된 경우 우선 사용
            raw_codes = [code.strip() for code in stock_codes_str.split(',')]
            # 유효한 6자리 숫자 종목코드만 필터링 및 중복 제거(입력 순서 보존)
            seen = set()
            valid_codes = []
            invalid_codes = []
            for c in raw_codes:
                if not c:
                    continue
                if c.isdigit() and len(c) <= 6:
                    if c not in seen:
                        seen.add(c)
                        valid_codes.append(c)
                else:
                    invalid_codes.append(c)

            active_stocks = valid_codes
            if invalid_codes:
                print(f"DEBUG WARNING: {len(invalid_codes)}개 유효하지 않은 종목코드 제거: {set(invalid_codes)}")
            print(f"DEBUG PRINT: `stock_codes` 파라미터로 대상을 한정합니다: {len(active_stocks)}개 종목 - {active_stocks}")
            # DB에 존재하는 종목만 남기도록 추가 검증
            if active_stocks:
                existing = db.query(Stock.stock_code).filter(Stock.stock_code.in_(active_stocks)).all()
                existing_set = {code for code, in existing}
                missing = [c for c in active_stocks if c not in existing_set]
                if missing:
                    print(f"DEBUG WARNING: {len(missing)}개 종목이 DB에 존재하지 않음: {missing}")
                # preserve original order
                active_stocks = [c for c in active_stocks if c in existing_set]
                if not active_stocks:
                    print("DEBUG WARNING: 제공된 모든 종목이 DB에 존재하지 않습니다. Task를 종료합니다.")
                    return None
        else:
            active_stocks = get_managed_stocks_from_db(db)
        # --- START: 디버깅 코드 v5 (루프 진입 확인) ---
        print(f"DEBUG PRINT: active_stocks len={len(active_stocks)}; sample={repr(active_stocks[:5])}")
        print("DEBUG PRINT: entering per-stock loop")
        # --- END: 디버깅 코드 v5 ---

        # =================================================================
        # BUG FIX: stock_limit을 DART 맵 로드 전에 적용하도록 위치 수정
        # =================================================================
        # stock_codes가 제공되지 않았을 때만 stock_limit 적용
        if not stock_codes_str and stock_limit > 0:
            active_stocks = active_stocks[:stock_limit]
            print(f"DEBUG PRINT: stock_limit={stock_limit} 적용 후, {len(active_stocks)}개 종목만 처리")

        # DART 고유번호 맵 로드
        force_update_map = kwargs.get('params', {}).get('force_update_map', False)
        print(f"DEBUG PRINT: DART 고유번호 맵 로드 시작 (force_update={force_update_map})")
        corp_map_df = get_corp_code_map(force_update=force_update_map)
        print(f"DEBUG PRINT: DART 고유번호 맵 로드 완료. {len(corp_map_df)}개 법인 정보 포함.")

        today = date.today()
        success_count = 0
        fail_count = 0
        skip_count = 0

        # 각 종목에 대해 순차 처리
        for idx, stock_code in enumerate(active_stocks, 1):
            # --- START: 디버깅 코드 v5 (루프 내부 확인) ---
            print(f"DEBUG PRINT: processing {stock_code} (idx={idx})")
            # --- END: 디버깅 코드 v5 ---
            logger.info(f"[{idx}/{len(active_stocks)}] {stock_code} 재무 분석 시작...")
            try:
                # 2-1. DART 고유번호 조회 (캐시 우선)
                corp_code = get_corp_code(stock_code, corp_map_df)
                # DEBUG: 어떤 stock_code가 어떤 corp_code로 매핑되는지 남깁니다.
                logger.debug(f"get_corp_code mapping: stock_code={stock_code} -> corp_code={corp_code!r}")
                if not corp_code:
                    print(f"DEBUG SKIP REASON: [{stock_code}] DART 고유번호 조회 실패, 건너뜀")
                    logger.warning(f"[{stock_code}] DART 고유번호 조회 실패, 건너뜀")
                    skip_count += 1
                    continue

                # 2-2. 재무 데이터 수집
                financials_raw, shares_raw = fetch_live_financial_data(corp_code)
                if not financials_raw:
                    print(f"DEBUG SKIP REASON: [{stock_code}/{corp_code}] 재무 데이터 없음, 건너뜀")
                    logger.warning(f"[{stock_code}/{corp_code}] 재무 데이터 없음, 건너뜀")
                    skip_count += 1
                    continue

                # 2-3. 데이터 파싱
                parser = _FinancialDataParser()
                financial_df = parser.parse(financials_raw, shares_raw or [])

                if financial_df.empty:
                    print(f"DEBUG SKIP REASON: [{stock_code}] 파싱 결과 비어있음, 건너뜀")
                    logger.warning(f"[{stock_code}] 파싱 결과 비어있음, 건너뜀")
                    skip_count += 1
                    continue

                # 2-4. 현재 유통주식수 추출
                current_list_count = 0
                if shares_raw:
                    for item in reversed(shares_raw):
                        if item.get('se') == '보통주':
                            distb_stock_co = item.get('distb_stock_co', '0')
                            try:
                                current_list_count = int(distb_stock_co.replace(',', ''))
                                break
                            except ValueError:
                                continue

                if current_list_count <= 0:
                    print(f"DEBUG SKIP REASON: [{stock_code}] 발행주식수 정보 없음, 건너뜀")
                    logger.warning(f"[{stock_code}] 발행주식수 정보 없음, 건너뜀")
                    skip_count += 1
                    continue

                # 2-5. EPS 계산
                calculator = _EpsCalculator()
                eps_df = calculator.calculate(financial_df, current_list_count)

                if eps_df is None or eps_df.empty:
                    print(f"DEBUG SKIP REASON: [{stock_code}] EPS 계산 실패, 건너뜀")
                    logger.warning(f"[{stock_code}] EPS 계산 실패, 건너뜀")
                    skip_count += 1
                    continue

                # 2-6. 재무 등급 판정
                analyzer = _FinancialGradeAnalyzer()
                result = analyzer.analyze(eps_df)

                # 2-7. DB에 UPSERT
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
                    f"[{stock_code}] 재무 분석 완료 - "
                    f"등급: {result.get('financial_grade')}, "
                    f"YoY: {result.get('eps_growth_yoy')}%, "
                    f"연평균: {result.get('eps_annual_growth_avg')}%"
                )

                # 2-8. DART API Rate Limiting
                time.sleep(0.5)

            except Exception as e:
                logger.error(f"[{stock_code}] 재무 분석 중 오류 발생: {e}", exc_info=True)
                fail_count += 1
                continue

        # 3. 모든 성공 건 커밋
        db.commit()

        print(
            f"DEBUG PRINT: 재무 분석 완료 - "
            f"성공: {success_count}, 실패: {fail_count}, 건너뜀: {skip_count}, "
            f"총: {len(active_stocks)}"
        )

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
        "stock_codes": Param(
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

