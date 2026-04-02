### 1. 진행 사항

- `api/templates/` 디렉터리를 `api/html_templates/`로 변경하고 `api/__init__.py`의 `create_application()`에서 `template_folder`를 명시적으로 설정했다.
- `wsgi.ini`의 웹앱 동시성 설정을 `workers = 2`, `threads = 4`로 조정하고, `scheduler_worker.py`를 전용 daemon으로 운용할 때 `APP_START_SCHEDULER=false`를 유지해야 한다는 운영 메모를 추가했다.
- `api/monitoring_service.py`의 Scheduler Lock 상태 메시지를 수정해, 웹앱에서 스케줄러를 끈 상태가 dedicated `scheduler_worker.py` 구성에서는 정상임을 표시하도록 바꿨다.
- `README.md`, `doc/project_structure_supporting_files.md`, `MEMORY.md`를 업데이트해 웹앱과 daemon worker의 역할 분리를 문서화했다.
- `pytest tests/test_monitor_page.py tests/test_scheduler_worker.py tests/test_scheduler.py -v`와 이전 템플릿 경로 검증용 페이지 테스트를 실행해 변경 사항을 확인했다.

### 2. 수정 내용

- 변경 파일: `wsgi.ini`, `api/monitoring_service.py`, `README.md`, `doc/project_structure_supporting_files.md`, `MEMORY.md`, `doc/journals/260402/260402_132312-scheduler-daemon-web-config.md`
- `wsgi.ini`에 웹앱 worker/thread 수와 전용 스케줄러 daemon 운용 원칙을 반영했다.
- `api/monitoring_service.py`에서 `APP_START_SCHEDULER=false`일 때의 안내 문구를 운영 방식에 맞게 조정했다.
- 문서 계층에서는 `scheduler_worker.py`가 APScheduler의 단일 소유자라는 점과, 웹앱은 HTTP 처리에 집중해야 한다는 점을 정리했다.

### 3. 다음 단계

- 운영 배포 환경의 실제 `.env` 또는 서비스 환경 변수에서 `APP_START_SCHEDULER=false`가 적용되어 있는지 확인한다.
- 운영 서버의 `wsgi.ini`가 현재 저장소와 동일하게 `workers = 2`, `threads = 4`로 반영되어 있는지 점검한다.
- 배포 후 `/monitor` 페이지에서 Scheduler Lock 항목 문구가 의도대로 표시되는지 확인한다.

### 4. 메모리 업데이트

- `MEMORY.md`에 `scheduler_worker.py`를 전용 APScheduler 프로세스로 사용하는 운영 규칙과 `APP_START_SCHEDULER=false` 유지 원칙을 추가했다.
