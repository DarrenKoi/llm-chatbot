---
tags: [wiki, log]
last_updated: 2026-05-01
status: in-progress
---

# Wiki Log

> 모든 ingest, query-saved, lint, manual-edit 작업의 이력.
> 매 작업 후 LLM 또는 사람이 1 항목을 prepend (최신이 위) 한다.

형식: `## [YYYY-MM-DD] <action> | <target>`

action: `ingest` | `query-saved` | `lint` | `manual-edit`

---

<!-- 새 항목은 이 위에 prepend -->

## [2026-05-01] ingest | raw/learning-logs/workflow_*.md, workflows.md, 워크플로_라우팅_확장_전략.md (by 대영)

- Added wiki/concepts/workflow-runtime-structure.md
- Added wiki/concepts/workflow-registration.md
- Added wiki/concepts/workflow-state-management.md
- Added wiki/concepts/workflow-authoring.md
- Added wiki/concepts/workflow-prompting.md
- Added wiki/concepts/workflow-routing-scaling.md
- Updated wiki/index.md (Concepts 섹션에 6 페이지 등록)
- Open question: `_compiled_graph` 단일 캐시의 정확한 식별자/위치 — 코드에서 변수명 확인 필요 (workflow-runtime-structure.md 의 Unverified 블록)
- Open question: 라우팅 확장 권장 schema(positive_examples, priority 등) 도입 시점 — 별도 ADR 필요 (raw/decisions/ 후보)
- Open question: `ChatState` 의 라우팅 메타 필드 추가 시 공유 상태 비대화 vs 도메인 라우터 분리 트레이드오프

## [2026-05-01] manual-edit | bootstrap

- LLM Wiki 부트스트랩. 폴더 구조와 SCHEMA 초기화.
- 첫 raw 자료 ingest 대기.
