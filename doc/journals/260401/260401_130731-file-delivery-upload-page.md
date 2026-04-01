# 1. 진행 사항
- 기존 `cdn` 기능을 `file_delivery`로 리네이밍하고, 업로드/다운로드 라우트를 `api/file_delivery/router.py` 기준으로 정리했다.
- `api/config.py`에서 `FILE_DELIVERY_*` 환경변수를 도입하고, 기존 `CDN_*` 값은 하위 호환 폴백으로 유지했다.
- `api/scheduled_tasks/tasks/cleanup.py`에 만료 파일 정리 잡 `cleanup_file_delivery`를 추가해 30일 보관 후 삭제 흐름을 연결했다.
- 사용자 요구에 맞춰 `/file-delivery` HTML 업로드 페이지를 추가하고, 브라우저 쿠키 `LASTUSER`를 기본 사용자 ID로 읽어 업로드에 사용하도록 구현했다.
- `api/file_delivery/file_delivery_service.py`에서 파일을 사용자별 경로(`original/<user>/<date>/...`)에 저장하도록 변경하고, 사용자별 최근 파일 목록 조회 함수 `list_files_for_user()`와 메타데이터 조회 함수 `get_file_metadata()`를 추가했다.
- 업로드 API `POST /api/v1/file-delivery/upload`가 `file_url`, `stored_filename`, `user_id`를 반환하도록 확장했고, 비이미지 다운로드 시 원본 파일명을 유지하도록 보완했다.
- 프로젝트 메모리 `MEMORY.md`를 갱신해 사내망 전용, 외부 차단, HTTP-only 환경 제약과 `file_delivery` 규칙을 기록했다.
- 검증으로 `pytest tests/test_index.py tests/test_scheduler_cleanup_task.py -v`, `pytest tests/test_index.py tests/test_main_page.py -v`, `pytest tests/ -v`를 실행했고 최종 전체 테스트 `71 passed`를 확인했다.
- 작업 결과를 다음 커밋으로 반영하고 원격 `main` 브랜치에 푸시했다.
  - `68af2bf file_delivery: 파일 전달 이름과 정리 작업 반영`
  - `bbe8fb7 memory: 사내망 HTTP 제약 조건 기록`
  - `07e86d1 file_delivery: 업로드 페이지와 사용자별 저장 경로 추가`

# 2. 수정 내용
- 변경 파일
  - `api/file_delivery/__init__.py`: `get_file_metadata`, `list_files_for_user` export 추가
  - `api/file_delivery/router.py`: `/file-delivery` 페이지 라우트, `LASTUSER` 기반 업로드 사용자 해석, 다운로드 시 원본 파일명 유지
  - `api/file_delivery/file_delivery_service.py`: 사용자별 저장 경로, 메타데이터 조회, 사용자 파일 목록 조회, 파일 URL 반환 보강
  - `api/templates/file_delivery.html`: 신규 업로드 UI, URL 복사 버튼, 최근 파일 목록, `LASTUSER` 쿠키 반영
  - `api/config.py`: `FILE_DELIVERY_*` 설정 도입 및 기본 URL을 `http://itc-1stop-solution-llm-webapp.aipp02.skhynix.com/file-delivery/files`로 정리
  - `api/scheduled_tasks/tasks/cleanup.py`: 만료 file delivery 파일 삭제 잡 추가
  - `tests/test_index.py`: 업로드/쿠키 사용자/사용자별 목록 테스트 추가
  - `tests/test_main_page.py`: `/file-delivery` 페이지 렌더링 테스트 추가
  - `tests/test_scheduler.py`: cleanup 잡 2개 등록에 맞춰 스케줄러 테스트 수정
  - `tests/test_scheduler_cleanup_task.py`: 만료 file delivery 정리 테스트 추가
  - `MEMORY.md`: 사내망 전용, HTTP-only, file delivery 규칙 반영
- 삭제/이동
  - `api/cdn/__init__.py` -> `api/file_delivery/__init__.py`
  - `api/cdn/cdn_service.py` -> `api/file_delivery/file_delivery_service.py`
  - `api/cdn/router.py` -> `api/file_delivery/router.py`

# 3. 다음 단계
- `/file-delivery` 페이지에서 생성된 URL을 Cube 메시지에 바로 붙여넣기 쉽게 하는 포맷 버튼 또는 템플릿 복사 기능을 추가한다.
- 서비스가 생성하는 이미지/문서 결과물을 `file_delivery` 저장소를 통해 업로드하고 URL을 Cube 응답에 포함하도록 연동한다.
- 현재 사용자 기준 파일 삭제, 재조회, 최근 업로드 목록 갱신 같은 관리 기능을 `/file-delivery` 페이지에 확장한다.
- 실제 사내 환경 브라우저에서 `LASTUSER` 쿠키 접근 가능 여부와 업로드 페이지 동작을 수동 확인한다.

# 4. 메모리 업데이트
- `MEMORY.md` 업데이트 완료.
- 반영 내용
  - 서비스와 Cube 연동은 사내망 전용이며 외부 인터넷에서는 접근할 수 없다는 제약
  - 운영 프로토콜은 HTTPS가 아니라 HTTP만 허용된다는 제약
  - `file_delivery` 업로드/조회 엔드포인트와 30일 보관 정책
