# 진행 사항
- `/monitor` 페이지에 `Primary Redis` 상태와 daemon 상태를 함께 표시하도록 모니터링 로직을 확장했다.
- `api/cube/worker.py`, `api/scheduler_worker.py`에서 activity log heartbeat를 남기도록 수정했다.
- `tests/test_monitoring_service.py`를 추가해 daemon 상태 판별을 단위 테스트로 검증했다.
- `pytest tests/test_monitoring_service.py tests/test_monitor_page.py tests/test_cube_worker.py tests/test_scheduler.py -v`를 실행해 관련 회귀를 확인했다.

# 수정 내용
- 변경 파일: `api/monitoring_service.py`
  - `Primary Redis` 상태 체크 추가
  - `Cube Worker Daemon`, `Scheduler Worker Daemon` 상태 체크 추가
  - activity log tail을 읽어 최근 `started`/`heartbeat` 이벤트 기준으로 `running`, `stale`, `not running` 판별 로직 추가
- 변경 파일: `api/cube/worker.py`
  - `cube_worker_started`에 `pid` 기록 추가
  - `cube_worker_heartbeat` 주기 로그 추가
- 변경 파일: `api/scheduler_worker.py`
  - `scheduler_worker_started`에 `pid` 기록 추가
  - `scheduler_worker_heartbeat` 주기 로그 추가
- 변경 파일: `api/html_templates/monitor.html`
  - 제목을 `Service Monitor`로 변경
  - Redis/daemon 모니터링 설명 문구로 수정
- 변경 파일: `api/html_templates/main.html`
  - 메인 페이지 하단 링크 문구를 `Service Monitor`로 수정
- 변경 파일: `tests/test_monitor_page.py`
  - 새 모니터링 항목이 화면에 렌더링되는지 검증하도록 갱신
- 변경 파일: `tests/test_monitoring_service.py`
  - daemon heartbeat 최신/오래됨/미존재 케이스 추가
- 변경 파일: `MEMORY.md`
  - 모니터링 규칙 및 daemon heartbeat 기준 추가

# 다음 단계
- 운영 환경에서 `cube_worker.py`, `scheduler_worker.py` daemon이 실제로 activity log heartbeat를 남기는지 확인한다.
- `/monitor`에서 `Primary Redis`, `Cube Worker Daemon`, `Scheduler Worker Daemon` 항목이 `running/connected`로 보이는지 배포 후 점검한다.
- stale 상태가 잦다면 heartbeat 주기와 stale 임계값을 환경에 맞게 조정할지 검토한다.

# 메모리 업데이트
- `MEMORY.md`에 `/monitor`의 Redis/daemon 판별 규칙과 worker heartbeat 규칙을 추가했다.
