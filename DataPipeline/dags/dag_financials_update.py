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

import pendulum
import json
import logging
from datetime import datetime

from airflow.models import DAG, Variable
from airflow.operators.python import PythonOperator
from airflow.exceptions import AirflowException
from airflow.models.param import Param

from sqlalchemy import text, func, and_
from sqlalchemy.dialects.postgresql import insert

from src.database import SessionLocal, FinancialAnalysisResult

logger = logging.getLogger(__name__)

DEFAULT_ARGS = {
    'owner': 'tradesmart_ai',
    'retries': 1,
    'retry_delay': pendulum.duration(minutes=10),
}


def _run_financials_update(**kwargs):
    params = kwargs.get('params', {})
    execution_mode = params.get('execution_mode', 'LIVE')
    logger.info(f"재무 분석 업데이트 시작: mode={execution_mode}")

    if execution_mode == 'SIMULATION':
        # --- SIMULATION 모드: 재무 데이터 스냅샷 준비 ---
        target_datetime_str = params.get('target_datetime')
        if not target_datetime_str:
            raise AirflowException("SIMULATION 모드에서는 'target_datetime' 파라미터가 필수입니다.")

        try:
            exec_dt = datetime.strptime(target_datetime_str, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            raise AirflowException("target_datetime 형식이 'YYYY-MM-DD HH:MM:SS'가 아닙니다.")

        db = SessionLocal()
        try:
            logger.info("SIMULATION 스냅샷에 재무 분석 데이터 포함을 시작합니다.")
            db.execute(text("TRUNCATE TABLE simulation.financial_analysis_results"))

            # test_stock_codes가 비어있으면 모든 종목 처리, 있으면 지정된 종목만 처리
            stock_codes_param = params.get('test_stock_codes', '') or ''
            if stock_codes_param.strip():
                stock_codes_list = [code.strip() for code in stock_codes_param.split(',') if code.strip()]
                filter_condition = FinancialAnalysisResult.stock_code.in_(stock_codes_list)
                logger.info(f"지정된 종목 대상으로 재무 스냅샷 생성: {len(stock_codes_list)}개")
            else:
                filter_condition = True  # 모든 종목
                logger.info("모든 종목 대상으로 재무 스냅샷 생성")

            # 종목별 latest(analysis_date <= exec_dt.date())만 선택하는 서브쿼리
            latest_per_stock_subq = (
                db.query(
                    FinancialAnalysisResult.stock_code,
                    func.max(FinancialAnalysisResult.analysis_date).label('max_date')
                )
                .filter(
                    FinancialAnalysisResult.analysis_date <= exec_dt.date(),
                    filter_condition
                )
                .group_by(FinancialAnalysisResult.stock_code)
                .subquery()
            )

            # 타겟 테이블을 simulation 스키마로 지정
            target_table = FinancialAnalysisResult.__table__
            original_schema = target_table.schema
            target_table.schema = 'simulation'
            try:
                # 서브쿼리와 조인하여 해당 시점 최신 레코드들만 선택
                source_query = (
                    db.query(
                        FinancialAnalysisResult.stock_code,
                        FinancialAnalysisResult.analysis_date,
                        FinancialAnalysisResult.eps_growth_yoy,
                        FinancialAnalysisResult.eps_annual_growth_avg,
                        FinancialAnalysisResult.financial_grade,
                        FinancialAnalysisResult.created_at,
                        FinancialAnalysisResult.updated_at,
                    )
                    .join(
                        latest_per_stock_subq,
                        and_(
                            FinancialAnalysisResult.stock_code == latest_per_stock_subq.c.stock_code,
                            FinancialAnalysisResult.analysis_date == latest_per_stock_subq.c.max_date,
                        )
                    )
                )

                insert_stmt = insert(target_table).from_select(
                    [
                        'stock_code',
                        'analysis_date',
                        'eps_growth_yoy',
                        'eps_annual_growth_avg',
                        'financial_grade',
                        'created_at',
                        'updated_at',
                    ],
                    source_query,
                )

                db.execute(insert_stmt)
                db.commit()
                # 커밋 후 행 수 확인
                total_rows = db.execute(text("SELECT COUNT(*) FROM simulation.financial_analysis_results")).scalar()
                logger.info(f"✅ 재무 분석 데이터 스냅샷 복제 완료: {total_rows} 행")
            finally:
                # 스키마 복원
                target_table.schema = original_schema

        finally:
            db.close()

    else:
        # --- LIVE 모드: 기존 로직 (현재 과업 범위 외) ---
        logger.info("LIVE 모드 재무 분석 실행 (기존 로직 유지)")
        # ... (기존 로직) ...


with DAG(
    dag_id='dag_financials_update',
    default_args=DEFAULT_ARGS,
    schedule_interval='0 2 * * 6',
    start_date=pendulum.datetime(2025, 1, 1, tz='Asia/Seoul'),
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

