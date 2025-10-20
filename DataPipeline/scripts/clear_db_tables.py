
from DataPipeline.src.database import Base, engine

print("모든 테이블을 삭제하고 재생성합니다...")

# 모든 테이블 삭제
Base.metadata.drop_all(bind=engine)
print("테이블 삭제 완료.")

# 모든 테이블 다시 생성
Base.metadata.create_all(bind=engine)
print("테이블 생성 완료.")

print("데이터베이스 초기화 완료.")
