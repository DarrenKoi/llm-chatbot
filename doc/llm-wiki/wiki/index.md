---
tags: [wiki, index]
last_updated: 2026-05-01
status: in-progress
---

# Wiki Index

> 이 위키의 전체 목차. 매 ingest 후 LLM 이 갱신한다.

## 시작점

- [overview.md](./overview.md) — 프로젝트 한눈에 보기
- [log.md](./log.md) — ingest/lint 이력
- [../WIKI_SCHEMA.md](../WIKI_SCHEMA.md) — 운영 규칙

## Components

<!-- 컴포넌트 페이지가 추가되면 여기에 link -->

_(아직 비어있음)_

## Runbooks

<!-- 운영 절차 페이지가 추가되면 여기에 link -->

_(아직 비어있음)_

## Concepts

<!-- 학습 개념 페이지가 추가되면 여기에 link -->

- [concepts/workflow-runtime-structure.md](./concepts/workflow-runtime-structure.md) — `start_chat` 루트 그래프 + 서브그래프 + checkpointer 모델
- [concepts/workflow-registration.md](./concepts/workflow-registration.md) — 패키지 자동 발견 기반 워크플로 등록 계약
- [concepts/workflow-state-management.md](./concepts/workflow-state-management.md) — 공유 `ChatState` vs 워크플로 전용 상태 분리
- [concepts/workflow-authoring.md](./concepts/workflow-authoring.md) — 새 워크플로 작성 절차와 `resolve → collect → execute` 패턴
- [concepts/workflow-prompting.md](./concepts/workflow-prompting.md) — `prompts.py` 책임 경계와 네이밍 규칙
- [concepts/workflow-routing-scaling.md](./concepts/workflow-routing-scaling.md) — 워크플로 수가 늘 때의 라우팅 확장 전략

## Decisions (ADR)

<!-- 합성된 ADR 페이지가 추가되면 여기에 link -->

_(아직 비어있음)_

## Sources

<!-- 원본 자료 인덱스 페이지가 추가되면 여기에 link -->

_(아직 비어있음)_
