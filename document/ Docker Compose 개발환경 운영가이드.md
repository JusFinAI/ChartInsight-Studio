네, 알겠습니다. 우리가 나눈 모든 논의와 전문가의 피드백을 종합하여, 앞으로 개발의 기준이 될 **최종판 워크플로우 가이드**를 문서로 만들어 드리겠습니다.

-----

# ChartInsight Studio: Docker Compose 실무 개발 워크플로우 가이드 (최종판)

### 1\. 개요

본 문서는 `ChartInsight Studio` 프로젝트의 Docker Compose 환경을 가장 효율적으로 운영하기 위한 실무 방법론과 추천 명령어를 정리합니다. 이 가이드의 목적은 불필요한 재시작과 빌드 시간을 최소화하여 개발 속도를 극대화하는 것입니다.

-----

### 2\. 핵심 개념: 서비스 그룹 분리 운영

우리 프로젝트는 개발 주기가 다른 두 개의 논리적 그룹으로 구성됩니다.

  * **WebApp 그룹 (`app` 프로필):** `backend`, `frontend` 서비스가 포함됩니다. 소스 코드 변경이 **빈번하게 발생**하는 그룹입니다.
  * **DataPipeline 그룹 (`pipeline` 프로필):** `airflow-*` 서비스들이 포함됩니다. 비교적 기능이 안정화되어 **변경이 간헐적으로 발생**하는 그룹입니다.

이 워크플로우의 핵심은 이 두 그룹을 독립적으로 관리하는 것입니다.

-----

### 3\. 코드 관리 방식: `build`와 `volumes`의 정밀한 역할

[cite\_start]서비스의 특성에 따라 코드를 관리하는 방식이 다르며, 두 가지 방식을 조합하여 개발 편의성을 극대화합니다[cite: 1, 2].

| 구분 (Category) | `backend` / `frontend` (`app` 프로필) | `DataPipeline` (Airflow) (`pipeline` 프로필) |
| :--- | :--- | :--- |
| **코드 포함 방식** | **이미지 빌드 (`build`) + 소스 코드 마운트 (`volumes`)** | [cite\_start]**사전 빌드된 이미지 (`image`) + 설정/데이터 마운트 (`volumes`)** [cite: 1] |
| **동작 원리** | 1. **`build` (기초 공사):** `Dockerfile`을 사용해 `npm install`, `pip install` 등 **의존성을 설치한 기본 환경 이미지**를 만듭니다.\<br\>2. **`volumes` (인테리어):** 로컬의 소스 코드 폴더(`- ./backend:/app`)를 컨테이너 내부에 **실시간으로 연결(마운트)하여, 코드 변경이 즉시 반영되도록 합니다(핫 리로딩). | 1. `image`: Docker Hub의 공식 `apache/airflow` 이미지를 그대로 사용합니다.\<br\>2. [cite\_start]`volumes`:** 로컬의 `dags`, `src` 폴더를 컨테이너에 **실시간으로 연결**하여 DAG 파일 등을 관리합니다[cite: 1]. |
| **`--build` 필요 시점** | [cite\_start]**의존성**(`package.json`, `requirements.txt`) 또는 \*\*`Dockerfile`\*\*이 변경되었을 때만 필요합니다[cite: 2]. | 기본적으로 **필요 없습니다.** |

-----

### 4\. 서비스 의존성 관리: `depends_on`과 `condition`

`depends_on`은 서비스 간의 실행 순서와 준비 상태를 제어하는 중요한 옵션입니다. 우리 프로젝트는 가장 안정적인 방식을 사용하고 있습니다.

  * **단순 `depends_on`:** 서비스의 **시작 순서**만 보장합니다.
  * [cite\_start]**`depends_on` + `condition: service_healthy` 👍:** 서비스가 `healthcheck`를 통과하여 **완전히 준비될 때까지** 다음 서비스의 시작을 기다립니다[cite: 4]. `backend`가 `postgres-tradesmart`에 대해 이 방식을 사용하므로, DB 연결 오류를 방지할 수 있습니다.

-----

### 5\. 최종 워크플로우: "무엇을 변경했는가?"

앞으로 개발 작업을 할 때, 무엇을 변경했는지에 따라 아래의 워크플로우를 따르시면 됩니다.

#### **상황 1: 단순 소스 코드만 변경했을 때 (`.py`, `.tsx` 등)**

  * **추천 행동:** **아무 명령어도 필요 없습니다\! 그냥 브라우저를 새로고침 하세요.**
  * [cite\_start]**이유:** `volumes` 옵션으로 소스 코드가 실시간 동기화되고, `uvicorn`이나 Next.js 개발 서버가 변경을 감지하여 \*\*자동으로 핫 리로딩(Hot-Reloading)\*\*을 수행하기 때문입니다[cite: 2].
  * **예외:** 핫 리로딩이 드물게 실패하는 경우, 아래 명령어로 해당 서비스만 가볍게 재시작할 수 있습니다.
    ```bash
    docker compose restart chartinsight_backend
    ```

#### **상황 2: 의존성 또는 `Dockerfile`을 변경했을 때 (`requirements.txt`, `package.json` 등)**

  * **추천 행동:** **이때만 `--build` 옵션을 사용합니다.**
    ```bash
    docker compose --profile app up -d --build
    ```
  * [cite\_start]**이유:** 의존성 설치는 이미지 자체에 '구워져야' 하는 '기초 공사'에 해당하므로, `--build`를 통해 이미지를 새로 만들어야 합니다[cite: 2]. [cite\_start]이 명령어는 **실행 중인 `pipeline` 컨테이너에는 영향을 주지 않습니다.** [cite: 2]

-----

### 6\. 전체 명령어 요약 (치트 시트)

| 목표 (Goal) | **단 하나의 명령어 (The Only Command You Need)** |
| :--- | :--- |
| **웹 앱**만 실행/재시작 | `docker compose --profile app up -d` |
| **데이터 파이프라인**만 실행/재시작 | `docker compose --profile pipeline up -d` |
| **모든 시스템** 함께 실행 | `docker compose --profile app --profile pipeline up -d` |
| **웹 앱 코드 수정 후** | **(없음) 브라우저 새로고침** 또는 `docker compose restart <서비스명>` |
| **웹 앱 의존성 수정 후** | `docker compose --profile app up -d --build` |
| **모든 시스템 종료** | [cite\_start]`docker compose down` (실행된 컨테이너만 종료) [cite: 3] |