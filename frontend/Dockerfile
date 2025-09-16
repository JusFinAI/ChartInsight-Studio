# 1. Node.js 18 버전의 가벼운(alpine) 공식 이미지를 기반으로 시작합니다.
FROM node:18-alpine

# 2. 컨테이너 안에서 작업할 기본 폴더를 /app 으로 지정합니다.
WORKDIR /app

# 3. 의존성 목록 파일들만 먼저 복사합니다. (백엔드와 같은 이유로 빌드 속도 향상)
COPY package.json ./
COPY package-lock.json ./

# 4. 의존성 목록을 보고 npm으로 라이브러리들을 설치합니다.
RUN npm install

# 5. 나머지 모든 소스 코드를 /app 폴더 안으로 복사합니다.
COPY . .

# 6. 컨테이너가 시작될 때, Next.js 개발 서버를 실행하라는 명령입니다.
#    (코드가 변경되면 웹 브라우저가 자동으로 새로고침됩니다.)
CMD ["npm", "run", "dev"]