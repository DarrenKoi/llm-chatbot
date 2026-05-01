---
tags: [concept, workflow, routing, scaling, classifier]
level: advanced
last_updated: 2026-05-01
status: in-progress
owner: 대영
sources:
  - raw/learning-logs/워크플로_라우팅_확장_전략.md
  - raw/learning-logs/workflows.md
  - api/workflows/start_chat/lg_graph.py
  - api/workflows/registry.py
---

# 워크플로 라우팅 확장 전략 (Workflow Routing at Scale)

> 워크플로가 많아질 때 답은 "키워드를 더 많이 넣기"가 아니라 "키워드를 다단계 라우팅의 한 층으로 격하시키기"다.

## 왜 필요한가? (Why)

- 현재 `classify_node` 는 사용자 메시지에 `handoff_keywords` 가 부분문자열로 들어있는지만 확인한다. 워크플로 3~5 개에서는 충분하지만 수십 개로 늘면 충돌·일반화 부족·맥락 누락이 빠르게 커진다 (`raw/learning-logs/워크플로_라우팅_확장_전략.md` §1).
- 모든 handoff 워크플로를 루트 그래프에 직접 컴파일해 붙이는 구조는 컴파일 시간·메모리·시각화 난도를 같이 키운다 (`raw/learning-logs/workflows.md` §6.2).
- 비슷한 다른 개념과의 차이: 일반 NLU 시스템(Rasa, Dialogflow CX 등)이 이미 정착시킨 패턴(confidence threshold, no-match, contextual scope, hierarchical intent)을 이 저장소 LangGraph 구조에 옮겨 적용한다.

## 핵심 개념 (What)

### 정의

라우팅 확장의 proper way 는 다음 세 축의 조합이다 (`raw/learning-logs/워크플로_라우팅_확장_전략.md` §10):

- **계층형**: `domain → workflow → slot-filling`
- **혼합형**: `rule + classifier/retrieval + fallback`
- **모듈형**: 얇은 루트 라우터 + 도메인 루트 + 서브그래프

### 관련 용어

- `규칙 라우터(Policy router)`: 단순 substring 매칭이 아니라 priority, negative keywords, requires_active_context, allowlist 등을 갖춘 명시적 규칙 엔진.
- `intent classifier`: 워크플로를 intent 로 보고 예시 문장(training phrases)으로 학습하거나 LLM 으로 분류.
- `semantic retrieval (top-k)`: 워크플로를 description/positive/negative 예시로 catalog 화하고, 사용자 발화와 가까운 후보를 top-k 로 검색.
- `LLM judge / selector`: top-k 후보 중 LLM 이 최종 선택.
- `clarification / fallback`: confidence 가 낮거나 top-2 점수 차가 작으면 사용자에게 의도를 되묻거나 no-match 처리.
- `domain root graph`: `language_root`, `travel_root`, `analytics_root` 같이 도메인별 상위 라우터 그래프.
- `lazy compile`: 무거운 워크플로는 진입 시점에 컴파일 또는 별도 실행 경계로 분리.

### 시각화 / 모델

권장 라우팅 파이프라인 (`raw/learning-logs/워크플로_라우팅_확장_전략.md` §5.1):

```text
사용자 입력
    │
    ▼
1. resume/interrupt 우선     ──► 진행 중 워크플로 재개
    │
    ▼
2. 명시 규칙 (cancel/stop, slash 명령 등)  ──► 즉시 처리
    │
    ▼
3. 도메인 후보 선택 (coarse classifier)
    │   language / travel / analytics / general_chat
    ▼
4. 워크플로 후보 선택 (semantic top-k or classifier)
    │
    ▼
5. low-confidence 또는 ambiguity → clarification
    │
    ▼
6. 최종 handoff → 서브그래프 진입
```

권장 그래프 구조:

```text
현재:                      권장:
  start_chat                start_chat (얇은 전역 라우터)
   ├── translator             ├── language_root
   ├── invoice_summary        │     ├── translator
   ├── incident_summary       │     ├── proofreader
   └── ...                    │     └── summarizer
                              ├── travel_root
                              │     └── ...
                              └── analytics_root
                                    └── ...
```

## 어떻게 사용하는가? (How)

### 단계별 도입 순서

(`raw/learning-logs/워크플로_라우팅_확장_전략.md` §6)

#### 1단계. 키워드 라우터를 "정책 라우터"로 승격

지금 바로 할 수 있는 최소 개선.

- `handoff_keywords` 외에 `priority`, `negative_examples`, `domain_id` 추가
- `classify_node()` 를 substring 루프에서 score 기반 룰 엔진으로 교체
- wrong-handoff / no-match 로그 수집
- ambiguous case 를 그냥 `start_chat` 으로 흘리지 말고 clarification 후보로 기록

#### 2단계. domain classifier + workflow catalog 추가

- domain 분류 추가
- workflow metadata catalog 구축 (description, positive/negative examples, required_slots 등)
- semantic retrieval 또는 lightweight classifier 로 top-k 후보 생성
- clarification flow 1급 시민으로

#### 3단계. hybrid router 완성

- 규칙 fast-path
- semantic top-k
- LLM selector / judge
- confidence + ambiguity threshold
- clarification / fallback

#### 4단계. 도메인별 루트 그래프 + lazy execution

- `start_chat` 을 얇게 유지
- 도메인 루트 그래프 도입 (`language_root` 등)
- 큰 워크플로 분리 배치
- tracing / observability 정비

### 권장 registry schema

`api/workflows/registry.py` 에 더할 메타데이터 (`raw/learning-logs/워크플로_라우팅_확장_전략.md` §5.2):

- `workflow_id`, `domain_id`, `display_name`, `description`
- `handoff_keywords`, `handoff_patterns`
- `positive_examples`, `negative_examples`
- `required_slots`, `supported_locales`
- `priority`, `allow_global_entry`
- `resume_policy`, `clarification_hint`

핵심: `handoff_keywords` 만으로 판단하지 말고 라우팅에 필요한 설명·운영 정책을 함께 저장.

### 실무 패턴

- **resume/interrupt 우선**: 진행 중인 thread 가 있으면 새 라우팅보다 재개가 우선.
- **fast-path 규칙**: cancel/stop, 운영 명령, slash 명령은 classifier 거치지 않고 즉시 처리.
- **상위 2 후보 점수 차로 ambiguity 판정**: 가장 높은 점수 - 두 번째 점수 < threshold 면 clarification.
- **catalog 기반 워크플로 등록**: 새 워크플로 추가 시 코드 변경 최소화. description / examples 작성에 더 시간 투자.
- **상태 관리 원칙**: 멀티턴 워크플로는 per-thread, 단발성은 per-invocation. 모든 워크플로가 같은 거대한 상태 dict 를 공유하지 않도록 ([workflow-state-management.md](workflow-state-management.md)).

### 주의사항 / 함정

- **추천하지 않는 방향** (`raw/learning-logs/워크플로_라우팅_확장_전략.md` §8):
  - 모든 워크플로를 계속 같은 루트 그래프에 직접 연결
  - 키워드 사전만 계속 키우기
  - confidence/ambiguity 개념 없이 classifier 를 바로 production 투입
  - fallback 없이 무조건 하나의 워크플로 강제 선택
  - metadata 없이 LLM 에 전체 워크플로 목록을 매번 던져 선택시키기
- **LLM judge 단독 라우터의 함정**: 후보가 너무 많으면 prompt 가 커지고 선택 품질이 떨어진다. "후보가 줄어든 뒤 최종 선택"에만 쓰는 편이 현실적.
- **상위 단계 오분기의 비대칭 비용**: 도메인 라우터에서 잘못 분기하면 하위 라우터·워크플로가 아무리 좋아도 복구 어려움. 도메인 taxonomy 설계가 부실하면 오히려 혼란이 커진다.
- **clarification 과용**: 너무 자주 뜨면 시스템이 멍청해 보인다. 임계값 튜닝 필수.
- **`_compiled_graph` 캐시 한계**: 현재 단일 캐시 구조에서는 새 워크플로 추가나 metadata 변경이 사실상 프로세스 재시작을 요구한다 (`raw/learning-logs/workflows.md` §8.3). hot-reload 가 필요하면 별도 설계.

> Unverified: 권장 메타데이터(positive_examples, negative_examples, priority 등)는 외부 NLU 시스템 관행을 이 저장소에 옮기자는 제안이며, 합성 시점(2026-05-01)의 `api/workflows/registry.py` 에는 아직 구현되지 않은 미래 schema 다. 실제 도입은 별도 ADR 로 진행할 것.

## 실무 체크리스트 (워크플로 추가 시 라우팅 관점)

- 이 워크플로는 어느 `domain_id` 에 속하는가
- 전역 진입 가능인가, 특정 컨텍스트에서만 가능인가
- 대표 예시 문장 10 개 이상이 준비됐는가
- 헷갈리기 쉬운 negative examples 가 있는가
- low-confidence 일 때 어떤 clarification 문구를 보여줄 것인가
- resume 가능한 멀티턴 워크플로인가
- 기존 워크플로와 충돌하는 trigger 가 있는가
- no-match / 오분류 관측 방안은

## 참고 자료 (References)

- 원본 메모:
  - [../../raw/learning-logs/워크플로_라우팅_확장_전략.md](../../raw/learning-logs/워크플로_라우팅_확장_전략.md)
  - [../../raw/learning-logs/workflows.md](../../raw/learning-logs/workflows.md) §6
- 관련 개념:
  - [workflow-runtime-structure.md](workflow-runtime-structure.md) — 현재 런타임 구조
  - [workflow-registration.md](workflow-registration.md) — 현재 `handoff_keywords` 기반 등록
  - [workflow-state-management.md](workflow-state-management.md) — 상태 경계 원칙
- 코드 경로:
  - `api/workflows/start_chat/lg_graph.py`
  - `api/workflows/registry.py`
- 외부 문서:
  - Dialogflow CX Intents — <https://docs.cloud.google.com/dialogflow/cx/docs/concept/intent>
  - Dialogflow ES Contexts — <https://docs.cloud.google.com/dialogflow/es/docs/contexts-overview>
  - Rasa Fallback Classifier — <https://rasa.com/docs/rasa/reference/rasa/nlu/classifiers/fallback_classifier/>
  - Rasa Two-Stage Fallback — <https://rasa.com/docs/rasa/2.x/reference/rasa/core/policies/two_stage_fallback/>
  - LangGraph Subgraphs — <https://docs.langchain.com/oss/python/langgraph/use-subgraphs>
  - AWS Step Functions Nested Workflows — <https://docs.aws.amazon.com/step-functions/latest/dg/concepts-nested-workflows.html>
  - LlamaIndex Routing Guide — <https://docs.llamaindex.ai/en/v0.12.15/module_guides/querying/router/>
  - Haystack ConditionalRouter — <https://docs.haystack.deepset.ai/docs/conditionalrouter>
