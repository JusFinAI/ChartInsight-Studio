

### **\[프로젝트 보고서\] ChartInsight Studio: 통합 개발 환경 구축 및 파이프라인 검증 상세 리포트**

문서 버전: 1.1  
작성일: 2025년 8월 6일  
작성자: Gemini (AI 기술 코치)

#### **1\. 프로젝트 개요**

본 문서는 ChartInsight Studio 풀스택 웹 애플리케이션의 로컬 개발 환경을 구축하고, 핵심 데이터 수집 파이프라인의 안정성을 검증하는 전 과정을 상세히 기록한다. 초기 비전 단계에서 나아가, 분산된 개발 환경을 전문가 수준의 통합 Docker 환경으로 전환하며 발생한 다양한 기술적 과제와 해결 과정을 통해, 견고하고 확장 가능한 개발 기반을 마련하였다.

#### **2\. 여정: 문제 해결을 통한 심층 학습**

2.1. 기반 다지기: 분산된 환경의 통합  
프로젝트 초기, 소스코드는 윈도우(frontend, backend)와 WSL2(DataPipeline)에 분산되어 있었다. 이는 효율적인 통합 테스트와 관리를 어렵게 만드는 근본적인 문제였다.

* **해결**: 모든 프로젝트 폴더를 WSL2 내부의 단일 루트 폴더(\~/ChartInsight-Studio)로 통합했다. 이 과정을 통해 현대적인 개발 방식인 모노레포(Monorepo) 구조의 기틀을 마련했으며, Git으로 전체 프로젝트의 버전 관리를 시작하여 '안전 금고'와 '타임머신' 기능을 확보했다.

2.2. WSL2 환경과의 사투: 의존성 문제 해결  
WSL2(Ubuntu 24.04)의 최신 Python(3.12) 환경은 backend 라이브러리 설치 과정에서 연쇄적인 문제를 발생시켰다.

* **distutils 누락 문제**: pip install 시 ModuleNotFoundError: No module named 'distutils' 에러가 발생했다. 이는 최신 Ubuntu에서 Python의 기본 패키지가 최소화되어 발생한 문제로, sudo apt-get install python3.12-venv 등 시스템 레벨의 패키지를 설치하여 해결을 시도했다.  
* **버전 비호환성 문제**: 시스템 패키지 설치 후에도 AttributeError: module 'pkgutil' has no attribute 'ImpImporter' 에러가 발생했다. 이는 requirements.txt에 명시된 구버전 라이브러리(numpy==1.24.3 등)가 최신 Python 3.12와 호환되지 않아 발생한 문제임을 최종적으로 진단했다.  
* **최종 해결**: requirements.txt에서 버전 고정을 제거하고, pip install \--upgrade pip setuptools wheel 명령으로 설치 도구 자체를 최신화하여, 현재 환경과 완벽하게 호환되는 최신 라이브러리들을 성공적으로 설치했다. 이 과정을 통해 **시스템 패키지(apt)와 애플리케이션 패키지(pip)의 차이점, 그리고 버전 호환성의 중요성**을 학습했다.

2.3. Docker 심층 탐험: 컨테이너 오케스트레이션 완성  
단순히 컨테이너를 실행하는 것을 넘어, 전체 애플리케이션을 유기적으로 관리하기 위해 Docker 환경을 재구성했다.

* **Dockerfile 작성**: frontend(Next.js)와 backend(FastAPI) 각각의 '개별 건물 설계도'인 Dockerfile을 작성했다. 이 과정에서 image (기성품)와 build (맞춤 제작)의 차이점을 학습했다.  
* **.dockerignore 최적화**: node\_modules, venv 등 불필요한 폴더를 빌드 과정에서 제외시키는 .dockerignore 파일을 추가했다. 이를 통해 거의 1GB에 육박하던 빌드 데이터 전송량(context)을 획기적으로 줄여, 빌드 속도를 높이고 file already closed와 같은 잠재적 오류를 원천 차단했다.  
* **Docker 환경 문제 해결**:  
  * Docker Desktop의 'WSL Integration' 설정을 활성화하여 WSL2 터미널에서 docker 명령어를 사용할 수 있도록 조치했다.  
  * docker compose down 시 네트워크가 정리되지 않는 문제를 docker network inspect, docker container prune 등 심화 명령어를 통해 '유령' 컨테이너를 찾아 제거함으로써 해결했다.  
* **docker-compose.yaml 최종 완성**: 기존에 검증된 DataPipeline의 설정을 기반으로, frontend, backend 서비스를 추가하고, **profiles 기능**을 도입하여 '웹 앱(app)'과 '데이터 파이프라인(pipeline)'을 독립적으로 실행할 수 있는 유연하고 강력한 최종 통합 설계도를 완성했다.

2.4. Airflow 고급 설정 및 검증  
데이터 파이프라인의 안정성과 정확성을 검증하며 Airflow의 핵심 개념을 학습했다.

* **상태 영속성(Persistence)**: docker compose down/up 이후에도 DAG의 활성화 상태가 유지되는 현상을 통해, Airflow가 자신의 모든 상태(State)를 외부 Docker 볼륨에 연결된 **메타데이터 DB에 저장**한다는 핵심 원리를 이해했다.  
* **airflow users create 명령어**: Airflow 이미지 버전이 동일함에도 불구, 과거와 달리 \--email 파라미터가 필수가 된 현상을 겪었다. 이는 Docker 이미지의 'Mutable Tag' 개념, 즉 **동일한 버전 태그(2.10.5)라도 내용물이 업데이트될 수 있다**는 실무적인 문제를 통해 학습했다.  
* **API 호출 제어**: 동시 실행되는 다수의 DAG가 API 서버에 과부하를 주는 것을 막기 위해, pool='kiwoom\_api\_pool' 설정을 코드에 추가하고, Airflow UI에서 해당 Pool을 생성했다. 스케줄러가 변경된 설정을 인지하지 못하는 문제를 \*\*서비스 재시작(down/up)\*\*으로 해결하며, 설정 변경 시 재시작이 필요할 수 있음을 배웠다.

#### **3\. 최종 검증 및 결과**

3.1. 데이터 파이프라인 (pipeline 프로필) 검증  
docker compose \--profile pipeline up \-d 명령어로 파이프라인을 성공적으로 실행했다. Airflow UI(http://localhost:8080)와 DBeaver를 통해 dag\_initial\_loader의 초기 적재가 완료되었고, 증분 DAG들이 스케줄에 맞춰 live.candles 테이블에 최신 데이터를 정상적으로 쌓는 것을 최종 확인했다.  
3.2. 웹 애플리케이션 (app 프로필) 검증  
모든 환경 정리가 끝난 후 docker compose \--profile app up \-d 명령어로 웹 앱을 성공적으로 실행했다.

* **백엔드**: http://localhost:8000/docs에서 FastAPI API 문서가 정상적으로 출력됨을 확인했다.  
* **프론트엔드**: http://localhost:3000에서 'Trading Radar' UI가 차트와 함께 성공적으로 렌더링됨을 확인했다.

#### **4\. 현재 상태 및 다음 단계**

* **현재 상태**: ChartInsight-Studio는 이제 **완벽하게 동작하는 풀스택 로컬 개발 환경**을 갖추었다. 개발자는 단일 docker-compose.yaml 파일과 프로필 명령어를 통해 원하는 작업 환경을 즉시 구성할 수 있으며, 소스코드 수정 시 실시간으로 변경사항이 반영되는 높은 생산성의 개발 워크플로우를 확보했다.  
* **다음 단계**: 이제 이 안정적인 통합 개발 환경 위에서 **본격적인 ChartInsight-Studio 기능 개발**을 시작한다. 다음 우선순위 과제는, backend가 매번 외부 API를 호출하는 현재 구조에서 벗어나, **DataPipeline이 postgres-tradesmart DB에 쌓아둔 데이터를 직접 조회하여 프론트엔드에 제공**하도록 로직을 수정하고 발전시키는 것이다.