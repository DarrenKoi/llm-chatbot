# 텍스트 청킹 & 전송 라우팅 레이어 구현

## 1. 진행 사항

- Cube 플랫폼의 ~45줄 강제 줄바꿈 문제 분석 및 해결 전략 수립
- LLM 응답을 콘텐츠 유형(텍스트/코드/표)별로 분리하여 전송 방법을 결정하는 청킹 모듈 설계
- LLM 기반 청킹 vs 규칙 기반 청킹 비교 후 규칙 기반 채택 (지연/비용 대비 이점 부족)
- multimessage + richnotification 조합 전송 전략 설계 (콘텐츠 유형별 라우팅)
- richnotification 미구현 상태를 고려하여 `CUBE_RICH_ROUTING_ENABLED` 토글 추가 (기본값: OFF)
- 21개 단위 테스트 작성 및 전체 통과 확인
- 설계 문서 작성 (`doc/텍스트_청킹.md`)

## 2. 수정 내용

### 신규 파일
- `api/cube/chunker.py` — 핵심 청킹 + 전송 라우팅 모듈
  - `plan_delivery()`: LLM 응답 → `DeliveryItem` 리스트 변환
  - `_parse_blocks()`: 코드 펜스 / 표 / 텍스트 블록 파싱
  - `_chunk_text()`: 문단/헤더 경계 기반 40줄 청킹
  - `_merge_adjacent()`: 인접 동일 method 항목 병합
- `tests/test_cube_chunker.py` — 21개 테스트 (기본 동작, rich ON/OFF, 청킹, 한국어, 병합)
- `doc/텍스트_청킹.md` — 설계 문서 (한국어)

### 수정 파일
- `api/config.py` — `CUBE_MESSAGE_MAX_LINES` (기본 40), `CUBE_RICH_ROUTING_ENABLED` (기본 false) 추가
- `api/cube/service.py` — `send_multimessage()` 단일 호출을 `plan_delivery()` 기반 루프로 교체
  - `plan_delivery` 실패 시 원본 텍스트로 fallback
  - rich routing ON 시 `send_richnotification()` 분기 전송
  - 대화 기록에는 원본 전체 텍스트 저장 (청킹은 전송 관심사만)

## 3. 다음 단계

- richnotification 전송 방법 구현 완료 후 `CUBE_RICH_ROUTING_ENABLED=true` 활성화
- 사무실에서 Cube 플랫폼으로 실제 긴 LLM 응답 전송 테스트 (40줄 분할 확인)
- 이미지/파일 링크의 richnotification 전송 구현 (사용자 계획)

## 4. 메모리 업데이트

텍스트 청킹 레이어 아키텍처 정보를 메모리에 추가 필요.
