# DataPipeline 단위 테스트 표준 가이드 (v1.0)

## 1. 목적

이 문서는 `DataPipeline` 프로젝트의 모든 단위 테스트가 일관되고, 신뢰할 수 있으며, 독립적인 환경에서 실행되는 것을 보장하기 위한 표준 방법론을 정의합니다. 모든 개발 주체(사용자, Gemini, `cursor.ai` 등)는 코드를 검증할 때 반드시 이 가이드를 따라야 합니다.

## 2. 핵심 원칙

- **독립성 (Independence)**: 단위 테스트는 외부 시스템(실제 DB, API, 네트워크 등)의 상태에 의존해서는 안 됩니다. 모든 외부 의존성은 '모킹(Mocking)'을 통해 제어되어야 합니다.
- **신속성 (Speed)**: 테스트는 개발 과정에서 수시로 실행되므로, 최대한 빨라야 합니다. 이를 위해 실제 DB 대신 인메모리(in-memory) DB를 사용합니다.
- **재현성 (Reproducibility)**: 테스트는 언제, 어디서 실행하든 항상 동일한 결과를 반환해야 합니다. 각 테스트는 실행 전에 독립적인 환경을 구축하고, 실행 후에 깨끗하게 정리해야 합니다.

## 3. 표준 테스트 실행 환경

아래의 환경 설정은 `unittest`가 우리 프로젝트의 모든 모듈을 정확히 찾고, 외부 시스템과 격리된 상태에서 테스트를 실행하기 위해 필수적입니다.

### 3.1. 가상환경 (Virtual Environment)

- **규칙**: 모든 `DataPipeline` 관련 테스트는 반드시 `DataPipeline/.venv` 가상환경을 활성화한 상태에서 실행합니다.
- **이유**: 이 가상환경에는 우리 코드가 의존하는 라이브러리(예: `apache-airflow==2.10.5`)가 정확한 버전으로 설치되어 있습니다. 다른 가상환경을 사용할 경우, 버전 불일치로 인한 예기치 않은 에러가 발생합니다.
- **활성화 명령어**:
  ```bash
  source /home/jscho/ChartInsight-Studio/DataPipeline/.venv/bin/activate
  ```

### 3.2. 환경 변수 (Environment Variables)

- **규칙**: 테스트 실행 시, 아래의 환경 변수들을 명시적으로 설정해야 합니다.

- **`DATABASE_URL`**
    - **설정**: `export DATABASE_URL='sqlite:///:memory:'`
    - **이유**: SQLAlchemy가 실제 PostgreSQL DB 대신, 테스트 실행 중에만 메모리에 생성되는 임시 SQLite DB를 사용하도록 강제합니다. 이는 테스트 속도를 비약적으로 향상시키고, 실제 개발 DB가 테스트 데이터로 오염되는 것을 방지합니다.

- **`PYTHONPATH`**
    - **설정**: `export PYTHONPATH='/home/jscho/ChartInsight-Studio:/home/jscho/ChartInsight-Studio/DataPipeline'`
    - **이유**: Python 인터프리터가 `from DataPipeline.dags...` 또는 `from src.utils...` 와 같은 import 구문을 올바르게 찾을 수 있도록, 모듈 검색 경로에 프로젝트의 최상위 루트와 소스 코드 루트를 모두 추가합니다. 이는 모든 `ModuleNotFoundError` 문제의 근본적인 해결책입니다.

## 4. 표준 테스트 실행 명령어

- **규칙**: `unittest`의 `discover` 기능을 사용하여 `DataPipeline/tests` 폴더 내의 모든 테스트를 한번에 실행합니다.
- **이유**: 이 방식은 새로운 테스트 파일이 추가되더라도, 명령어 수정 없이 자동으로 테스트 스위트에 포함시켜주는 확장성 높은 방법입니다.

### 최종 표준 명령어 (One-Liner)

아래 명령어는 프로젝트 루트(`/home/jscho/ChartInsight-Studio`)에서 실행해야 하며, 위에서 설명한 모든 환경 설정과 테스트 실행을 한번에 수행합니다.

```bash
source /home/jscho/ChartInsight-Studio/DataPipeline/.venv/bin/activate && \
export PYTHONPATH='/home/jscho/ChartInsight-Studio:/home/jscho/ChartInsight-Studio/DataPipeline' && \
export DATABASE_URL='sqlite:///:memory:' && \
python -m unittest discover -v DataPipeline/tests
```

## 5. 요약

이 가이드를 준수함으로써, 우리는 안정적이고 신뢰할 수 있는 테스트 문화를 정착시키고, 결과적으로 더 높은 품질의 소프트웨어를 더 빠르게 개발할 수 있습니다.
