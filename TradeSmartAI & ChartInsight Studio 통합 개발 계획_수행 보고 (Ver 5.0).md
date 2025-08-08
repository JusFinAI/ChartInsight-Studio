### **TradeSmartAI & ChartInsight Studio 통합 개발 계획/수행 보고 (Ver 5.0)**

버전: 5.0  
작성일: 2025년 8월 7일  
작성자: Gemini AI (AI 기술 코치)

#### **1\. 프로젝트 개요**

본 프로젝트는 "TradeSmartAI" 데이터 파이프라인을 기반으로, 개인 투자자에게 전문가 수준의 실시간 차트 분석 기능을 제공하는 웹 서비스 \*\*"ChartInsight Studio"\*\*를 구축하는 것을 최종 목표로 한다.

Ver 4.0까지는 안정적인 데이터 수집 파이프라인 구축에 중점을 두었으나, Ver 5.0부터는 수집된 데이터를 활용하는 **풀스택 웹 애플리케이션 개발**로 프로젝트의 범위가 공식적으로 확장되었다. 본 문서는 확장된 목표에 맞춰 재구성된 개발 환경, 진화된 아키텍처, 그리고 수정된 최종 배포 전략을 종합적으로 기록한다.

#### **2\. 기술 스택 (확장)**

| 구분 | 기술 | 목적 |
| :---- | :---- | :---- |
| **Orchestration** | Apache Airflow | 데이터 수집 파이프라인 자동화 |
| **Database** | PostgreSQL | 주식 데이터(OHLCV) 및 Airflow 메타데이터 저장 |
| **Backend** | FastAPI (Python 3.x) | 웹 애플리케이션 비즈니스 로직 및 API 서버 |
| **Frontend** | Next.js (TypeScript) | 사용자 인터페이스(UI) 및 차트 시각화 |
| **Development Env.** | Docker Desktop with WSL2 | 컨테이너 기반의 통합 로컬 개발 환경 |

#### **3\. 단계별 계획 및 수행 보고**

3.1. 1단계: 핵심 로직 및 프로토타입 검증 (완료)  
1단계에서는 데이터 파이프라인의 핵심 기능과 웹 애플리케이션의 프로토타입을 각개전투 방식으로 개발하고 그 가능성을 검증했다.

* **데이터 파이프라인**: Kiwoom API를 통해 OHLCV 데이터를 수집하고 PostgreSQL에 저장하는 Airflow DAG의 핵심 로직을 완성하고, dag\_initial\_loader와 dag\_live\_collectors를 통해 초기 적재 및 증분 업데이트 기능을 구현했다.  
* **웹 애플리케이션 프로토타입**: FastAPI와 Next.js를 사용하여 Trading Radar 페이지의 핵심 UI와 Peak/Valley 탐지 알고리즘 등 주요 기능을 상당 수준 구현했다. 이 단계에서는 데이터베이스 연동 없이 API 직접 호출 및 더미 데이터를 활용하여 기능의 실현 가능성을 검증했다.

3.2. 2단계: 풀스택 통합 개발 환경 구축 및 파이프라인 안정화 (완료)  
이번 단계는 분산되어 있던 각 구성 요소를 전문가 수준의 단일 통합 개발 환경으로 구축하고, 실제 운영을 위한 안정성을 확보하는 데 중점을 두었다. 이 과정에서 발생한 수많은 기술적 난제를 해결하며 시스템의 완성도를 비약적으로 높였다.

* **프로젝트 구조 통합**: 윈도우와 WSL2에 분산되어 있던 frontend, backend, DataPipeline 폴더를 WSL2 내부의 단일 루트 폴더(\~/ChartInsight-Studio)로 통합하고, 전체 프로젝트를 단일 Git 저장소에서 관리하는 모노레포 구조의 기반을 마련했다.  
* **Docker 환경 재구성**:  
  * **통합 오케스트레이션**: 프로젝트 전체를 총괄하는 마스터 docker-compose.yaml 파일을 루트에 생성했다. 이 과정에서 기존에 검증된 DataPipeline의 설정을 존중하되, frontend와 backend 서비스를 추가하고 **Profiles 기능**을 도입하여 '웹 앱(app)'과 '데이터 파이프라인(pipeline)'을 독립적으로 실행할 수 있는 유연성을 확보했다.  
  * **이미지 최적화**: frontend와 backend를 위한 Dockerfile을 각각 작성하고, node\_modules, venv 등 불필요한 파일을 빌드에서 제외하는 .dockerignore 파일을 추가하여 이미지 용량을 최적화하고 빌드 속도를 향상시켰다.  
* **환경 문제 심층 해결**:  
  * **WSL2 & Docker**: Docker Desktop의 'WSL Integration' 설정 오류를 해결하고, docker container prune, docker network inspect 등 심화 명령어를 통해 반복적으로 발생하던 '유령' 컨테이너 및 네트워크 문제를 완전히 해결하여 깨끗하고 안정적인 실행 환경을 확보했다.  
  * **Python 의존성**: WSL2(Ubuntu 24.04) 환경에서 발생한 distutils 누락 및 버전 비호환성 문제를 시스템 패키지(apt)와 애플리케이션 패키지(pip)의 차이점을 학습하며 해결했다. pip 등 빌드 도구 자체를 업그레이드하여 최종적으로 의존성 설치를 완료했다.  
* **파이프라인 안정성 확보 및 검증**:  
  * Airflow의 Pool 기능을 airflow-init을 통해 자동으로 생성하도록 설정하여, 다수의 DAG가 동시에 실행되어도 API 호출이 안전하게 순차적으로 처리되도록 보장했다.  
  * docker compose \--profile pipeline up \-d 명령어로 파이프라인을 실행하여, Airflow UI와 DBeaver 양쪽에서 증분 데이터가 스케줄에 맞춰 누락 없이 꾸준히 쌓이는 것을 최종 검증했다.  
* **풀스택 환경 구동 성공**: docker compose \--profile app up \-d 명령어로 frontend, backend, DB 컨테이너를 성공적으로 실행했다. localhost:3000에서 Next.js UI가, localhost:8000/docs에서 FastAPI API가 정상적으로 동작함을 확인하며, **완벽한 풀스택 로컬 개발 환경 구축을 완료**했다.

3.3. 3단계: ChartInsight Studio MVP 기능 완성 (진행 중)  
이제 안정적으로 구축된 통합 개발 환경 위에서 ChartInsight Studio의 핵심 기능을 완성하는 단계이다.

* **핵심 과제**: backend가 DataPipeline이 수집하여 PostgreSQL에 저장한 데이터를 직접 조회하여 frontend에 제공하도록 데이터 흐름을 연결한다. (현재는 API 직접 호출 또는 더미 데이터 사용)  
* **주요 활동**:  
  * backend에 SQLAlchemy ORM을 이용한 DB CRUD(Create, Read, Update, Delete) 로직 구현.  
  * frontend의 API 요청에 따라 backend가 DB에서 데이터를 조회하여 전달하도록 수정.  
  * 사용자 패턴 라벨링 기능 구현 및 DB 저장.

3.4. 4단계: PaaS 기반 프로토타입 배포 (계획 수정)  
초기 계획이었던 IaaS(GCP) 기반 배포는 MVP 단계에 비해 과도한 복잡성과 초기 비용을 유발할 수 있다고 판단하여, 더 빠르고 효율적인 PaaS 기반 배포로 전략을 수정한다.

* **목표**: MVP 기능이 완성된 ChartInsight Studio를 실제 사용자들이 접근할 수 있도록 인터넷에 배포한다.  
* **핵심 활동**:  
  * **Frontend 배포**: Next.js에 최적화된 **Vercel** 플랫폼을 사용하여 배포.  
  * **Backend & DB 배포**: **Railway**와 같은 PaaS를 사용하여 FastAPI 서버와 PostgreSQL 데이터베이스를 배포.  
  * **CI/CD 구축**: Github에 코드를 Push하면 자동으로 Vercel과 Railway에 새로운 버전이 배포되도록 파이프라인을 구성.

3.5. 5단계: IaaS 기반 확장 운영 (장기 계획)  
PaaS 배포를 통해 서비스의 시장성을 검증하고 사용자가 충분히 확보된 이후, 더 높은 수준의 확장성과 제어권을 위해 IaaS(GCP/AWS) 환경으로의 마이그레이션을 고려한다. 이 단계는 장기적인 비전으로 남겨둔다.