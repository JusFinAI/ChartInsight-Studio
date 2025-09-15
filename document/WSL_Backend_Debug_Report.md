# WSL 환경하 백엔드 디버그 환경 구축 시도 및 현황 (업데이트 Ver 2.0)

작성자: Grok-4-0709 (AI 코딩 어시스턴트)
작성일: 2025-08-28 (업데이트: 2025-08-28)

이 문서는 WSL2 환경에서 `backend` 서비스를 VS Code / Cursor에서 편리하게 Run & Debug(런치 구성)를 통해 디버깅할 수 있도록 설정을 시도한 모든 단계, 관찰된 문제, 재현 방법, 진단 결과 및 권장 해결책을 상세히 정리합니다. 사용자와의 대화 경험을 바탕으로 업데이트되었으며, 자동 워크플로우의 지속적 실패와 성공적인 수동 방법을 반영했습니다. 다른 개발자나 지원팀에 상황 전달용으로 사용하세요.

---

## 1) 목표
- WSL2(원격)에서 `backend`(FastAPI / uvicorn) 애플리케이션을 VS Code/Cursor의 Run & Debug 버튼(`Run & Attach Backend`, `Run Backend (uvicorn) and wait for debugger` 등)을 통해 수동 명령 없이 바로 디버깅할 수 있는 환경을 구축한다.
- 디버거: `debugpy`(venv 내부)
- 제약: 프로젝트 루트에 `backend`, `frontend`, 기타 디렉터리가 공존. `.env` 파일 사용. 원격 WSL2 경로와 로컬(Windows) 경로 혼동 가능.
- 업데이트 노트: 자동 워크플로우는 ECONNREFUSED 에러로 실패했으나, 수동 방법은 안정적으로 성공. 대안으로 수동 방법을 우선 추천.

## 2) 환경 요약
- OS: Windows + WSL2 (Ubuntu)
- 프로젝트 루트: `/home/jscho/ChartInsight-Studio`
- 백엔드 가상환경: `/home/jscho/ChartInsight-Studio/backend/venv` (Python 3.12)
- debugpy 설치: `/home/jscho/ChartInsight-Studio/backend/venv/lib/python3.12/site-packages/debugpy` (버전 1.8.16, 확인됨)
- VS Code / Cursor 확장: Python(ms-python.python, 버전 2023.6.0 ~ 2025.6.1 시도), Remote - WSL 사용
- 주요 포트: uvicorn 8000, debugpy attach 포트 5679 ~ 5684 (변경 시도)
- 추가: Docker 컨테이너 (frontend, postgres, airflow) 가 포트 충돌 원인일 수 있음 – 중지 후 테스트 추천.

## 3) 지금까지 시도한 주요 변경 및 조정 (업데이트: 대화 기반 추가)
- `.vscode/launch.json` 변경 시도 (여러 버전):
  - `--reload` 제거, -Xfrozen_modules=off 추가.
  - envFile, cwd backend 지정, subProcess: true.
  - type python/debugpy 변경, args with --listen, --wait-for-client, --log-to-stderr.
  - program to venv python, module to debugpy, host to 127.0.0.1/0.0.0.0/localhost.
  - port 변경 (5679 -> 5684).
  - env with DATABASE_URL to avoid RuntimeError.
  - pathMappings 강화.
  - preLaunchTask with delay-2s 추가.
- `.vscode/tasks.json` 변경: wait-for-debugger, delay-2s task 추가.
- venv에서 수동 실행 (성공 케이스):
  - `./venv/bin/python -Xfrozen_modules=off -m debugpy --listen 5680 --wait-for-client -m uvicorn app.main:app --host 127.0.0.1 --port 8000` (환경 변수 export DATABASE_URL 추가로 RuntimeError 방지).
  - VS Code에서 Attach 실행 → 연결 성공, 브레이크포인트 동작.
- 확장 재설치 (Python, Remote - WSL).
- netsh port forwarding (Windows CMD): listenport=5683 to connectport=5683.
- Docker 중지 (compose down) for port conflict.
- pyenv 확인: 설치되지 않음 (command not found).

업데이트 노트: 수동은 안정적, 자동은 ECONNREFUSED로 실패. Docker 중지, 포트 변경, netsh에도 불구.

## 4) 관찰된 문제들 (재현 가능한 핵심 증상)
1. Run & Attach 자동 워크플로우 실패.
   - UI 에러: "Could not find debugpy path" (초기), "ECONNREFUSED 127.0.0.1:568x" (후기).
   - Task timeout (포트 열림 대기 실패).
   - ss -ltn | grep 568x: 출력 없음 (포트 리스닝 실패).
2. Sources 탭에서 WSL 파일 안 보임 (경로 mismatch).
3. 수동 실행은 성공, 자동은 실패 (attach 불일치).
4. RuntimeError (DATABASE_URL not set) – env 설정으로 해결.

## 5) 주요 진단 포인트(원인 추정, 업데이트)
- Race condition: Attach가 포트 열림을 기다리지 못함.
- Path/extension mismatch: WSL 경로 혼동.
- Port conflict: Docker 컨테이너, 이전 프로세스 점유.
- WSL2 loopback issue: 127.0.0.1 연결 불안정 (netsh로 시도).
- 확장 버전: 2023.6.0 ~ 2025.6.1, debugpy 1.6.6 내부 번들 사용 (venv 1.8.16 무시).
- 업데이트: Docker 중지 후에도 ECONNREFUSED – WSL2 네트워크 or 확장 버그 가능성.

## 6) 수집된 로그/명령(참고, 업데이트 추가)
- debugpy 확인: exe /home/jscho/ChartInsight-Studio/backend/venv/bin/python, debugpy /home/jscho/ChartInsight-Studio/backend/venv/lib/python3.12/site-packages/debugpy/__init__.py.
- ss -ltn | grep 568x: 출력 없음 (포트 미리스닝).
- Output "Python": Could not find debugpy path, ECONNREFUSED.
- 수동 실행 로그: Uvicorn running on http://127.0.0.1:8000.
- netsh show all: 성공 (listenport=5683).

## 7) 권장 해결책(우선순위 순서, 업데이트 추가)
1. **수동 디버깅 사용** (성공 확인됨, 추천):
   - 환경 변수: export DATABASE_URL="postgresql+psycopg2://tradesmart_db:1234@localhost:5433/tradesmart_db".
   - 실행: ./venv/bin/python -Xfrozen_modules=off -m debugpy --listen 5680 --wait-for-client -m uvicorn app.main:app --host 127.0.0.1 --port 8000.
   - Attach: Run and Debug 패널에서 Attach 구성 실행.
2. **포트 정리**:
   - pkill -f debugpy ; pkill -f uvicorn.
   - ss -ltn | grep 568x for 확인.
3. **netsh 포워딩** (Windows CMD 관리자):
   - netsh interface portproxy add v4tov4 listenport=5683 listenaddress=127.0.0.1 connectport=5683 connectaddress=127.0.0.1.
4. **확장/ Cursor 재시작**:
   - Python / Remote - WSL 재설치 + Cursor 재부팅.
5. **WSL 재부팅** (Windows CMD):
   - wsl --shutdown.
   - Cursor 재시작 후 워크스페이스 재연결.
6. **대안**: Docker 중지 상태에서 수동 디버깅 사용, or Cursor 지원팀 문의 (로그 첨부).

## 8) 재현 절차
1. Cursor에서 WSL 워크스페이스 열기.
2. "Run Backend" 실행 – 서버 로그 확인.
3. "Attach" 실행 – ECONNREFUSED 에러 재현.
4. 수동 실행 for 대안.

## 9) 권장 launch.json (최종 버전, 성공 사례 기반)
(원본 예시 유지, 성공 args 추가)

## 10) 공유할 정보 for 추가 진단
- Output "Python" 로그, ss 출력, docker ps, netsh show all.

## 11) 결론 & 학습 포인트 (새 섹션)
- 자동 워크플로우는 WSL2 네트워크 이슈로 실패, 수동 방법은 안정적.
- 학습: WSL2 디버깅은 포트 포워딩, 확장 업데이트 필수. Docker와의 호환 확인.
- 다음 단계: 수동 방법으로 개발 진행, 필요 시 Cursor 커뮤니티/지원 문의.



