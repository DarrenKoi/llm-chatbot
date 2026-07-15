### 1. 진행 사항

- Arize Phoenix를 현재 Flask/LangGraph 서비스에 적용할 수 있는지 코드베이스와 공식 문서를 기준으로 검토하고, 결과를 `doc/llm-wiki/raw/learning-logs/20260715-arize-phoenix-observability-assessment.md`에 정리했다.
- Phoenix는 별도 Flask/FastAPI 래퍼 없이 자체 `phoenix serve` 서버로 실행하고, 운영 환경에서는 기존 Cube worker 및 scheduler worker와 동일하게 uWSGI 부착 데몬으로 관리하기로 결정했다.
- Phoenix 저장소는 MongoDB를 사용할 수 없으므로 단일 호스트·단일 Phoenix 인스턴스 조건에서 SQLite를 사용하도록 구성했다. SQLite 파일은 영구 로컬 볼륨에 있어야 하며, 여러 Phoenix 인스턴스가 공유해서는 안 된다.
- `phoenix_worker.py`의 `prepare_sqlite_storage()`에서 `PHOENIX_WORKING_DIR`을 생성하고 실제 쓰기 가능 여부를 검사하도록 구현했다. SQLite 파일과 스키마는 Phoenix가 최초 기동 시 자동 생성 및 마이그레이션한다.
- Phoenix 18.0.0 실기동 검증에서 SQLite migration, HTTP 서버, OTLP gRPC 서버가 정상적으로 시작되는 것을 확인했다. `GET /healthz`는 `200 OK`를 반환했고 종료도 정상 처리됐다.
- 선택적 코드 sandbox provider를 모두 비활성화해 사내망 기동 시 WASM binary 등의 외부 리소스를 내려받지 않도록 구성했다.
- 전체 테스트 결과는 `443 passed, 1 skipped`였다. skip된 항목은 사내 영구 볼륨 경로가 제공될 때만 실행하는 office-cloud 검사다. `ruff check .`, 변경 Python 파일 대상 `ruff format --check`, `pip check`, `git diff --check`도 통과했다.
- 구현과 문서 작업은 `8318bea`, `9b2bf7f`, `60a61c8`, `a277c66` 커밋으로 `main` 브랜치에 반영하고 원격 저장소로 push했다.

### 2. 수정 내용

- `phoenix_worker.py`
  - 프로젝트 `.env` 로드, Phoenix working directory 결정, 디렉터리 생성 및 쓰기 검사, SQLite URL 기본값 설정, Phoenix CLI 탐색과 `phoenix serve` process 전환을 구현했다.
  - 사내 `/project/workSpace`가 존재하면 기본 경로로 `/project/workSpace/phoenix-data`를 사용하고, 로컬에서는 `var/phoenix-data`를 사용한다.
- `wsgi.ini`
  - `attach-daemon = python phoenix_worker.py`를 추가해 Flask/uWSGI 기동 시 Phoenix도 형제 데몬으로 실행되도록 했다.
- `requirements.txt`
  - `arize-phoenix==18.0.0`을 추가했다.
- `.env.example`
  - `PHOENIX_WORKING_DIR`, HTTP/gRPC port, 7일 retention, 인증, strong password policy, telemetry 및 external resource 차단 설정을 추가했다.
  - 예시의 `ChangeMe-*` 값은 사내 배포 전에 반드시 실제 secret과 관리자 초기 비밀번호로 교체해야 한다.
- `scripts/sync_to_bitbucket.py`, `tests/test_sync_to_bitbucket.py`
  - 사내 동기화 대상에 `phoenix_worker.py`가 포함되도록 수정하고 복사 테스트를 보강했다.
- `tests/test_phoenix_worker.py`
  - 저장 경로 생성, SQLite URL 설정, 명시적 DB URL 보존, 잘못된 경로 거부, Phoenix executable 탐색, `os.execv()` 경계를 mock 기반으로 검증하는 단위 테스트를 추가했다.
- `tests/test_phoenix_worker_cloud.py`
  - `PHOENIX_OFFICE_TEST_DIR`이 제공된 경우 실제 사내 경로의 생성 및 쓰기 가능 여부를 검사하는 office 전용 테스트를 추가했다.
- `pyproject.toml`, `tests/conftest.py`
  - 사용하지 않는 Phoenix pytest plugin을 비활성화하고 테스트 중 로컬 `.env` 파일 로딩을 차단해 홈 디렉터리 권한과 개발자별 secret에 테스트 결과가 좌우되지 않도록 했다.
- 현재 단계에서는 Phoenix 서버, SQLite 저장소, 인증 설정과 daemon lifecycle만 연결했다. `api/llm/service.py`의 `ChatOpenAI` 호출과 `api/workflows/lg_orchestrator.py`의 LangGraph 실행은 아직 Phoenix로 trace를 전송하지 않는다.

### 3. 다음 단계

- 사내 서버에서 영구 로컬 볼륨 후보를 다음 명령으로 검증한다.

  ```bash
  PHOENIX_OFFICE_TEST_DIR=/project/workSpace/phoenix-data \
  pytest tests/test_phoenix_worker_cloud.py -v
  ```

- `/project/workSpace/phoenix-data`가 container 재배포 후에도 유지되는 writable local volume인지 확인한다. ephemeral filesystem, 공유 NFS 또는 여러 Phoenix replica가 같은 SQLite 파일을 사용하는 구성은 피한다.
- 사내 `.env`에서 `PHOENIX_SECRET`과 `PHOENIX_DEFAULT_ADMIN_INITIAL_PASSWORD`를 안전한 값으로 교체하고 `6006` 및 `4317` port 충돌과 내부 방화벽 정책을 확인한다.
- `pip install -r requirements.txt` 후 `uwsgi --ini wsgi.ini`로 기동하고, uWSGI log와 Phoenix `GET /healthz`, UI 접속 및 재기동 후 데이터 유지 여부를 확인한다.
- 사내 서비스 검증이 끝나면 별도 작업으로 OpenTelemetry/OpenInference tracing을 초기화하고 `ChatOpenAI`와 LangGraph를 instrument한다. 운영 Flask와 devtools는 같은 Phoenix 서버를 사용하되 서로 다른 project name 또는 환경 attribute로 구분한다.
- trace 연결 시 prompt, response, 사용자 식별자 및 tool argument에 대한 마스킹/수집 정책을 먼저 확정한다.

### 4. 메모리 업데이트

변경 없음
