## 1. 진행 사항
- 연속 번역 요청에서 후속 메시지가 이전 원문 대신 현재 질문 문장으로 해석되는 원인을 분석했다.
- `api/workflows/translator/nodes.py`의 상태 전이와 source text 파싱 로직을 점검해 완료 직후 후속 요청 처리 취약점을 수정했다.
- `tests/test_translator_workflow.py`에 연속 언어 전환 후속 요청 회귀 테스트 2건을 추가했다.
- `pytest tests/test_translator_workflow.py -v`와 `pytest tests/ -v`를 실행해 전체 테스트 통과를 확인했다.
- 변경 사항을 `translator: 연속 번역 후속 요청 안정화` 커밋으로 기록하고 `main` 브랜치에 push했다.

## 2. 수정 내용
- 변경 파일: `api/workflows/translator/nodes.py`
- 변경 파일: `tests/test_translator_workflow.py`
- `translate_node()` 완료 시 다음 턴이 항상 `entry`에서 다시 시작되도록 `next_node_id="entry"`를 설정했다.
- `_resolve_translation_request()`에서 `state.status == "completed"`인 경우를 별도로 처리해, 언어만 바꾼 후속 요청이면 직전 `source_text`를 재사용하고 새 원문이 있으면 이전 `target_language`를 재사용하지 않도록 수정했다.
- `_extract_source_text()`에 후속 요청 잡음 표현 정리 로직을 추가해 `이번엔 영어로 번역해줘` 같은 입력에서 `이번엔`이 원문으로 오인되지 않도록 보강했다.
- 한국어 조사 패턴을 확장해 `영어로도`, `일본어로는` 같은 표현도 목표 언어로 안정적으로 인식하도록 `_POSTPOSITIONS`를 보완했다.
- 추가 테스트:
- `test_translator_workflow_reuses_previous_source_for_language_only_follow_up()`
- `test_translator_workflow_does_not_reuse_previous_target_for_new_source_text()`
- 검증 결과:
- `pytest tests/test_translator_workflow.py -v` 통과
- `pytest tests/ -v` 통과
- Git 결과:
- commit `6a699de`
- push 대상 `origin/main`

## 3. 다음 단계
- Cube 실제 대화 흐름에서 `"안녕하세요"를 일본어로 번역해줘` 직후 `이번엔 영어로 번역해줘` 시나리오를 한 번 더 수동 검증한다.
- 운영 중 수집되는 후속 표현이 더 있으면 `api/workflows/translator/nodes.py`의 후속 요청 정규화 토큰 목록을 보강한다.

## 4. 메모리 업데이트
- 변경 없음
