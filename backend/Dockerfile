# 1. 파이썬 3.10 버전의 가벼운(slim) 공식 이미지를 기반으로 시작합니다.
FROM python:3.10-slim

# 2. 컨테이너 안에서 작업할 기본 폴더를 /app 으로 지정합니다.
WORKDIR /app

# 3. 먼저 의존성 목록(requirements.txt)만 복사합니다.
#    (소스코드가 바뀌지 않고 의존성만 그대로일 때, Docker가 이 부분을 캐시하여 빌드 속도를 높입니다.)
COPY requirements.txt .

# 4. 의존성 목록을 보고 pip으로 라이브러리들을 설치합니다.
RUN pip install --no-cache-dir -r requirements.txt

# 5. 나머지 모든 소스 코드를 /app 폴더 안으로 복사합니다.
COPY . .

# 6. 컨테이너가 시작될 때, uvicorn 서버를 실행하라는 명령입니다.
#    --host 0.0.0.0: 컨테이너 외부에서 접속을 허용합니다.
#    --reload: 소스코드가 변경되면 서버를 자동으로 재시작합니다. (개발용)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]