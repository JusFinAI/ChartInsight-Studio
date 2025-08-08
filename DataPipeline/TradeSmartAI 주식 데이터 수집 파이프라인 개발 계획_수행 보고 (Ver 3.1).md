### **TradeSmartAI 주식 데이터 수집 파이프라인 개발 계획/수행 보고 (Ver 3.1)**

* **버전:** 3.1  
* **작성일:** 2025년 7월 6일  
* **작성자:** Gemini AI (코칭 및 문서화 지원)

### **1\. 프로젝트 개요**

"TradeSmartAI" 웹 서비스의 핵심 기반이 될 주식 데이터 수집 파이프라인을 구축하는 것을 목표로 한다. 키움증권 REST API를 통해 국내 주식 종목들의 OHLCV 데이터를 수집하고, PostgreSQL 데이터베이스에 저장하며, Apache Airflow로 전체 프로세스를 자동화한다.

* **궁극적 목표:**  
  * 안정적이고 신뢰할 수 있는 주식 데이터 저장소 구축.  
  * 자동화된 데이터 수집 및 DB 업데이트 프로세스 확립.  
  * 향후 AI 기능 개발을 위한 견고한 데이터 기반 마련.

---

### **2\. 기술 스택**

* **오케스트레이션:** Apache Airflow (Docker Compose 기반 로컬 환경)  
* **데이터베이스:** PostgreSQL (Docker 컨테이너)  
* **데이터 수집:** 키움증권 REST API  
* **개발 언어:** Python 3.x  
* **환경:** Docker Desktop with WSL2

---

### **3\. 단계별 계획 및 수행 보고**

#### **3.1. 1단계: 로컬 개발 및 검증 (완료)**

* **목표:** 모든 데이터 수집 및 DB 저장 로직, 그리고 Airflow 워크플로우를 로컬 개발 환경에서 완벽하게 구현하고 테스트하여 안정성을 확보하는 것.  
* **수행 보고 및 주요 성과:**  
  * **통합 개발 환경 안정화:** docker-compose.yaml을 통해 Airflow와 PostgreSQL 서비스가 분리된 안정적인 로컬 개발 환경을 구축하고 검증했다. 파일 권한(UID/GID), 모듈 경로(PYTHONPATH), 서비스 초기화(airflow-init) 등 복잡한 인프라 문제를 모두 해결했다.  
  * **프로토타입 개발 및 검증:** data\_collector\_test.py 및 data\_collector\_test\_dag.py를 통해 단일 종목에 대한 데이터 수집-저장-자동화의 전체 흐름을 성공적으로 구현하고 검증했다. 이 과정에서 종목 정보 자동 적재 로직을 DAG에 통합하는 성과를 거두었다.  
  * **(추가 성과) 테스트 데이터 생성 유틸리티 개발:** prepare\_test\_data.py를 개발하여, 30개 타겟 종목 전체에 대한 5가지 타임프레임(5분, 30분, 1시간, 일, 주)의 테스트 데이터를 Parquet 형식으로 일괄 생성하는 기능을 완성했다. 총 150개의 테스트 파일 생성을 완료하여, 시뮬레이션 환경의 기반을 완벽하게 구축했다.  
  * **(추가 성과) 전체 파이프라인 아키텍처 설계 완료:** 프로토타입 개발 경험을 바탕으로, initial(초기 적재)과 incremental(증분 업데이트) 기능이 분리되고, 로컬 CLI와 Airflow 환경 모두에서 동작하는 '컨텍스트 인지형' 아키텍처를 PRD Ver 3.2로 최종 설계했다.

#### **3.2. 2단계: 전체 파이프라인 확장 개발 (계획)**

* **목표:** PRD Ver 3.2를 기반으로, 30개 종목을 처리하고 LIVE/SIMULATION 모드를 모두 지원하는 최종 data\_collector.py와 Airflow DAG 세트를 구현한다.  
* **핵심 활동:**  
  1. **data\_collector.py 개발 및 단위 테스트:**  
     * PRD에 명시된 load\_initial\_history 및 collect\_and\_store\_candles 함수를 구현한다.  
     * CLI 인터페이스(initial, incremental 커맨드)를 통해 각 기능의 동작을 로컬 환경에서 개별적으로 검증한다.  
  2. **dag\_simulation\_tester.py 개발 및 통합 테스트:**  
     * data\_collector.py의 모든 기능이 시뮬레이션 환경의 시간 흐름 속에서 멱등성을 유지하며 안정적으로 동작하는지 통합 테스트를 진행한다.  
     * BranchPythonOperator를 활용한 조건부 Task 실행 로직을 검증한다.  
  3. **운영용 DAG 세트(초기적재/증분) 개발:**  
     * 통합 테스트가 완료된 data\_collector.py를 사용하여, 실제 운영을 위한 6개의 DAG(dag\_initial\_loader.py 1개 \+ 증분용 5개)를 최종 개발한다.  
     * Dynamic DAG 패턴과 Airflow Pool 적용을 검증한다.

#### **3.3. 3단계: GCP 시험 운영 (계획)**

* **목표:** 로컬에서 완벽하게 검증된 주식 데이터 수집 파이프라인을 Google Cloud Platform (GCP) 환경에 배포하고, 실제 클라우드 환경에서 24시간 안정적으로 데이터가 수집 및 업데이트되는지 확인한다.  
* **핵심 활동:**  
  * **인프라 구축:** Compute Engine(Airflow 호스팅), Cloud SQL(PostgreSQL 호스팅) 등 GCP 리소스 생성 및 네트워크 설정.  
  * **파이프라인 배포:** 로컬의 프로젝트 코드를 Compute Engine으로 이전하고, .env 파일을 GCP 환경에 맞게 수정.  
  * **시스템 구동 및 모니터링:** docker-compose를 통해 GCP에서 Airflow 서비스를 실행하고, Cloud Logging 및 Cloud Monitoring을 통해 파이프라인 상태를 실시간으로 감시.  
  * **비용 최적화:** GCP 서비스 비용을 주기적으로 모니터링하고 리소스를 최적화.