import pendulum
from airflow.models.dag import DAG
from airflow.operators.python import PythonOperator
from sqlalchemy.dialects.postgresql import insert
import logging

from src.database import SessionLocal, Sector
from src.kiwoom_api.services.master import get_sector_list


def _update_sector_master_task():
    logger = logging.getLogger(__name__)
    logger.info("업종 마스터 데이터 업데이트를 시작합니다.")

    all_sectors = get_sector_list()

    if not all_sectors:
        raise ValueError("API로부터 업종 데이터를 가져오지 못했습니다. Task를 실패 처리합니다.")

    logger.info(f"총 {len(all_sectors)}개의 업종 데이터를 수집했습니다. DB 동기화를 시작합니다.")

    db = SessionLocal()
    try:
        # UPSERT 로직: sector_code가 존재하면 name과 market_name을 업데이트, 없으면 새로 삽입
        stmt = insert(Sector).values(all_sectors)
        update_stmt = stmt.on_conflict_do_update(
            index_elements=['sector_code'],
            set_={
                'sector_name': stmt.excluded.sector_name,
                'market_name': stmt.excluded.market_name
            }
        )
        db.execute(update_stmt)
        db.commit()
        logger.info(f"{len(all_sectors)}개 업종 데이터 DB 동기화 완료.")
    except Exception as e:
        db.rollback()
        logger.error(f"업종 마스터 저장 중 오류 발생: {e}")
        raise
    finally:
        db.close()


with DAG(
    dag_id='dag_sector_master_update',
    start_date=pendulum.datetime(2025, 1, 1, tz="Asia/Seoul"),
    schedule_interval='0 2 * * 6',  # 매주 토요일 오전 2시
    catchup=False,
    tags=['Master', 'Weekly'],
    doc_md="매주 Kiwoom API를 통해 전체 업종 마스터 데이터를 수집하고 DB에 동기화하는 DAG"
) as dag:
    update_sector_master = PythonOperator(
        task_id='update_sector_master_task',
        python_callable=_update_sector_master_task,
    )


