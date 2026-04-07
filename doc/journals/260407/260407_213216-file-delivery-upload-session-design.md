# 1. 진행 사항
- `llm_chatbot/api/file_delivery/file_delivery_service.py`, `llm_chatbot/api/file_delivery/router.py`, `llm_chatbot/api/html_templates/file_delivery.html`를 확인해 현재 file delivery 업로드/다운로드 구조를 점검했다.
- `llm_chatbot/api/workflows/start_chat/lg_graph.py`를 확인해 `start_chat` 워크플로가 최근 사용자 파일 URL을 LLM 컨텍스트에 주입하는 현재 방식을 확인했다.
- `rg -n "file_delivery|upload" -S .`, `sed`, `nl`, `git diff -- MEMORY.md` 명령으로 관련 구현, 테스트, 설정, 메모리 변경 내역을 검토했다.
- Cube에서는 사용자가 파일 업로드/다운로드를 직접 수행할 수 없다는 제약을 전제로, 대화 중 문서 제출이 필요할 때는 사용자 전용 웹 업로드 페이지 URL을 안내하는 방식이 적절하다는 설계 방향을 정리했다.
- 구현 제안으로 `upload_session` 기반의 대화 스코프 업로드 세션, `/file-delivery/session/<token>` 페이지, `user_id + channel_id` 검증, 짧은 TTL의 signed access URL 또는 서버 내부 조회 방식을 제안했다.

# 2. 수정 내용
- `llm_chatbot/MEMORY.md`에 다음 규칙을 추가했다.
  - Cube 대화창 자체에서는 사용자가 파일 업로드/다운로드를 직접 수행할 수 없다고 가정한다.
  - LLM이 파일 제출을 요청해야 할 때는 Cube 안에서 처리하지 말고, 사용자 전용 웹 업로드 페이지 URL을 안내하는 흐름으로 설계한다.
- `llm_chatbot/doc/journals/260407/260407_213216-file-delivery-upload-session-design.md` 파일을 새로 생성했다.
- 생산 코드 변경은 이번 세션에서 수행하지 않았고, 기존 `file_id` 기반 공개 다운로드 경로의 보안 리스크와 대화 비스코프 파일 주입 문제를 설계 이슈로만 정리했다.

# 3. 다음 단계
- `file_delivery`에 `upload_session` 메타데이터 저장소를 추가하고 `user_id`, `channel_id`, `purpose`, `expires_at`, `status`를 관리한다.
- `/file-delivery/session/<token>` 페이지와 대응 업로드 API를 추가해 `LASTUSER`와 세션 소유자를 검증한다.
- `llm_chatbot/api/workflows/start_chat/lg_graph.py`의 파일 컨텍스트 로직을 전체 사용자 파일이 아니라 현재 대화(`user_id + channel_id`) 기준으로 제한한다.
- 현재 `GET /file-delivery/files/<file_id>` 공개 접근 경로를 owner/session 검증 또는 short-lived signed URL 기반으로 재설계한다.

# 4. 메모리 업데이트
- `llm_chatbot/MEMORY.md`에 Cube 파일 업로드/다운로드 제약과 웹 업로드 페이지 유도 규칙을 추가했다.
