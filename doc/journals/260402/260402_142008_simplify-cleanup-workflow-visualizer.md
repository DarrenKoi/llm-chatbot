# Simplify 리뷰 + scan_member_info 제거 + 워크플로 그래프 시각화

## 진행 사항

- `/simplify` 코드 리뷰 실행 — 최근 5커밋의 변경사항 점검
- `APP_START_SCHEDULER=false` 설정이 올바른지 확인 (전용 daemon 구성에서 정상)
- `scan_member_info` 기능 전체 제거 (사용자 요청)
- `api/monitoring_service.py`에서 `from __future__ import annotations` 제거 (프로젝트 규칙 위반)
- pyvis 기반 워크플로 그래프 시각화 기능 추가 (`/workflows`, `/workflows/<workflow_id>` 라우트)
- 7개 워크플로 그래프에 정적 edge map 추가

## 수정 내용

### scan_member_info 전체 제거
- **삭제**: `api/scheduled_tasks/scan_member_info/` (패키지 전체)
- **삭제**: `tests/test_hynix_member_info_service.py`
- **수정**: `api/config.py` — `SCAN_MEMBER_INFO_*` 변수 6개 제거
- **수정**: `api/monitoring_service.py` — `_check_scan_member_info_redis()` 함수 및 entries 항목 제거
- **수정**: `api/scheduled_tasks/_registry.py` — `_TASK_PACKAGES`에서 항목 제거 (빈 리스트로 유지)
- **수정**: `.env.example` — scan member info 블록 제거
- **수정**: `README.md` — SCAN_MEMBER_INFO 환경변수 참조 제거
- **수정**: `tests/test_scheduler_worker.py` — scan_member_info 관련 테스트 2개 및 import 제거
- **수정**: `CLAUDE.md` — 아키텍처 섹션에서 scan_member_info 참조 제거
- **수정**: `doc/project_structure_api.md` — 디렉터리 목록에서 제거

### from __future__ import annotations 제거
- **수정**: `api/monitoring_service.py` — 프로젝트 규칙 위반 import 제거

### 워크플로 그래프 시각화 (pyvis)
- **생성**: `api/workflows/graph_visualizer.py` — pyvis 기반 HTML 그래프 생성 서비스
- **수정**: `api/__init__.py` — `/workflows`, `/workflows/<workflow_id>` 라우트 추가
- **수정**: `requirements.txt` — `pyvis` 패키지 추가
- **수정**: 7개 `graph.py` 파일에 `edges` 리스트 추가:
  - `api/workflows/start_chat/graph.py`
  - `api/workflows/sample/graph.py`
  - `api/workflows/chart_maker/graph.py`
  - `api/workflows/ppt_maker/graph.py`
  - `api/workflows/at_wafer_quota/graph.py`
  - `api/workflows/recipe_requests/graph.py`
  - `api/workflows/common/graph.py`

## 다음 단계

- 사무실 환경에서 `/workflows` 페이지 실제 렌더링 확인
- `from __future__ import annotations`가 남아있는 ~30개 파일 일괄 정리 (별도 커밋)
- 운영 `.env`에서 `SCAN_MEMBER_INFO_*` 변수 정리 확인

## 메모리 업데이트

- `CLAUDE.md` 아키텍처 섹션에서 `scan_member_info` 참조 제거 완료
- 워크플로 시각화 관련 메모리 추가 필요 여부 확인 필요
