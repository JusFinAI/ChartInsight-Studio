# 공식 Airflow 이미지를 기반으로 사용
FROM apache/airflow:2.10.5

# 루트 사용자로 전환하여 패키지 설치 권한 확보
USER root

# python-Levenshtein의 빠른 컴파일을 위해 C 빌드 도구 설치
RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*

# 다시 Airflow 사용자로 전환
USER airflow

# 로컬의 requirements.txt를 컨테이너 내부로 복사
COPY requirements.txt /requirements.txt

# 복사한 requirements.txt를 사용하여 패키지 설치
RUN pip install --no-cache-dir -r /requirements.txt


