# Arize Phoenix observability 적용성 검토

- 조사일: 2026-07-15
- 범위: 현재 Flask + Redis Cube worker + LangGraph + `langchain-openai` 구조에 Phoenix OSS 적용 가능성 검토
- 결론: **적용 가능하며, 워크플로/LLM 디버깅에는 분명한 이점이 있다.** 다만 Phoenix tracing만으로 응답 품질을 판정하거나 큐·데몬·인프라를 감시하고 경보를 보내지는 못한다. 따라서 기존 JSONL/상태 모니터링은 유지하고, Phoenix는 먼저 trace 분석 계층으로 추가하는 것이 안전하다.

## 1. 현재 코드와의 적합성

현재 실행 환경은 Python 3.11, `langchain==1.2.15`, `langchain-core==1.3.0`, `langchain-openai==1.1.14`, `langgraph==1.1.8`, `openai==2.32.0`이며 Phoenix/OpenTelemetry/OpenInference 패키지는 아직 설치되어 있지 않다. `requirements.txt:10-15`에는 LangChain/LangGraph 패키지가 버전 고정 없이 선언되어 있다.

Phoenix는 OpenTelemetry(OTLP)와 OpenInference를 사용하고, 공식적으로 LangGraph를 `openinference-instrumentation-langchain`의 `LangChainInstrumentor`로 지원한다. 이 instrumentor는 `langchain-core` callback manager에 연결되므로, 현재 `StateGraph` 및 `ChatOpenAI` 구조와 직접 맞는다. [Phoenix LangGraph tracing](https://arize.com/docs/phoenix/integrations/python/langgraph/langgraph-tracing), [OpenInference LangChain source](https://raw.githubusercontent.com/Arize-ai/openinference/main/python/instrumentation/openinference-instrumentation-langchain/src/openinference/instrumentation/langchain/__init__.py)

현재 핵심 실행 경계는 다음과 같다.

| 현재 seam | 근거 | Phoenix 적용 방식 |
| --- | --- | --- |
| LangGraph 전체 턴 | `api/workflows/lg_orchestrator.py:164-232`의 `handle_message()`와 `graph.invoke()` | LangChain instrumentor + 안전한 최상위 agent/chain span |
| 세션 연결 | `api/workflows/langgraph_checkpoint.py:17-22`의 사용자+채널 `thread_id` | `using_session()`에 원문 대신 HMAC 등 가명 ID 사용 |
| 중앙 LLM 호출 | `api/llm/service.py:179-329`, `725-822`의 `ChatOpenAI.invoke()` | 첫 단계에서는 LangChain instrumentor만 사용 |
| 일반 대화 RAG | `api/workflows/start_chat/rag/retriever.py:4-7`의 plain stub | 향후 manual `RETRIEVER` span 필요 |
| MCP/local tool | `api/mcp_client/executor.py:13-40`의 자체 실행기 | 향후 manual `TOOL` span 필요 |
| HTTP→worker | `api/cube/service.py:62-152`, `api/cube/queue.py:193-237` | 큐 payload에 trace context가 없어 현재는 하나의 분산 trace로 연결되지 않음 |

특히 `wsgi.ini:15-19,41-45`는 Flask worker 2개와 별도 Cube/scheduler daemon을 실행한다. 따라서 Flask 앱 초기화 한 곳에서만 tracing을 켜면 실제 LLM을 실행하는 Cube daemon이 계측되지 않는다. tracing 초기화는 **각 실제 프로세스에서 한 번씩**, 대상 라이브러리 사용 전에 실행되어야 한다. 초기 MVP의 최상위 span은 `handle_message()` 내부에 두는 편이 좋다. 이 함수는 `api/cube/service.py:188-207`의 thread pool 안에서 실행되므로 OpenTelemetry context가 별도 thread로 전달되지 않는 문제도 피할 수 있다.

## 2. 실제로 쉬워지는 것과 남는 것

Phoenix trace UI에서는 한 번의 대화 턴 안에서 LangGraph/chain/model 호출의 부모-자식 관계, 지연 시간, 오류, 입력·출력, 모델 속성 및 제공되는 경우 token usage를 함께 볼 수 있다. 현재 분리된 workflow JSONL과 LLM JSONL보다 “어느 노드/호출에서 시간이 걸리거나 fallback이 발생했는가”를 추적하기 쉬워진다. Phoenix도 trace를 실행 흐름과 소요 시간을 설명하는 기능으로 정의한다. [Phoenix overview](https://arize.com/docs/phoenix)

그러나 다음은 별도 문제다.

- trace는 “무슨 일이 있었는지”는 보여주지만 “응답이 좋은지”를 자동 판정하지 않는다. 품질에는 code evaluator, LLM judge, human annotation, dataset/experiment가 필요하다. [Phoenix evaluations](https://arize.com/docs/phoenix/evaluation/evals), [evaluation quickstart](https://arize.com/docs/phoenix/get-started/get-started-evaluations)
- Phoenix OSS 문서는 production traffic의 지속 평가와 threshold/alerting이 필요한 경우 Arize AX Online Evals를 안내한다. Phoenix를 완전한 APM/알림 시스템으로 간주하면 안 된다. [Phoenix evaluations](https://arize.com/docs/phoenix/evaluation/evals)
- Redis queue backlog, stale/duplicate 처리, daemon heartbeat, Mongo/Redis 상태는 기존 `api/monitoring_service.py`와 activity logs의 책임으로 유지해야 한다.

## 3. 권장 패키지와 현재 API

2026-07-15 확인 기준 최신 공개 버전은 아래와 같다. 실제 반영 시에는 최신을 무조건 따라가기보다, 현재 환경과 검증한 조합을 constraints/lock으로 고정한다.

| 목적 | 패키지/API | 확인 버전 |
| --- | --- | --- |
| 앱 측 OTLP 설정/전송 | `arize-phoenix-otel`, `from phoenix.otel import register` | 0.16.1 |
| LangChain + LangGraph 계측 | `openinference-instrumentation-langchain` | 0.1.67 |
| privacy `TraceConfig`/helpers | `openinference-instrumentation` | 0.1.54 |
| 선택적 OpenAI SDK 계측 | `openinference-instrumentation-openai` | 0.1.52 |
| 별도 self-host 서버 | `arize-phoenix` 또는 `arizephoenix/phoenix` image | 18.0.0 |

출처: [Phoenix OTEL PyPI](https://pypi.org/project/arize-phoenix-otel/), [LangChain instrumentor PyPI](https://pypi.org/project/openinference-instrumentation-langchain/), [OpenInference core PyPI](https://pypi.org/project/openinference-instrumentation/), [OpenAI instrumentor PyPI](https://pypi.org/project/openinference-instrumentation-openai/), [Phoenix server PyPI](https://pypi.org/project/arize-phoenix/).

`arize-phoenix-otel>=0.16.0`의 `register()`는 `project_name`, `batch`, `endpoint`, `protocol`, `headers`, `auto_instrument`를 지원하고 session/user/metadata/tags 및 manual span helpers를 제공한다. [Phoenix OTEL setup](https://arize.com/docs/phoenix/tracing/how-to-tracing/setup-tracing/setup-using-phoenix-otel), [0.16 release note](https://arize.com/docs/phoenix/release-notes/04-2026/04-24-2026-phoenix-otel-python-0-16)

현재 패키지 manifest상 Python 범위는 `>=3.10,<3.15`, LangChain instrumentor는 `langchain_core>=0.3.9`, OpenAI instrumentor는 `openai>=2.8.0`이므로 관찰된 환경은 선언상 호환된다. 그래도 structured output, tool calling, interrupt/resume를 포함한 실제 테스트는 필요하다. [LangChain manifest](https://raw.githubusercontent.com/Arize-ai/openinference/main/python/instrumentation/openinference-instrumentation-langchain/pyproject.toml), [OpenAI manifest](https://raw.githubusercontent.com/Arize-ai/openinference/main/python/instrumentation/openinference-instrumentation-openai/pyproject.toml)

## 4. LangGraph와 OpenAI-compatible `base_url`

첫 단계에는 `arize-phoenix-otel` + `openinference-instrumentation-langchain`만 권장한다. 이 저장소의 모든 LLM 호출은 `ChatOpenAI`를 거치므로 LangChain 계층에서 그래프와 LLM 호출을 함께 볼 수 있다. `generate_reply_intent()`는 structured 호출 실패 시 raw-text 호출을 한 번 더 하므로(`api/llm/service.py:226-258`), trace에서 실제 2회 호출과 fallback 비용도 확인할 수 있다.

선택적 OpenAI instrumentor는 hostname을 sniff하는 proxy가 아니라 Python SDK의 `OpenAI.request`/`AsyncOpenAI.request`를 감싼다. 따라서 custom `base_url` 자체가 계측을 막지는 않는다. 하지만 소스상 `llm.system`은 OpenAI로 기록하고, `llm.provider`는 알려진 host를 추론할 때만 추가한다. 사내 OpenAI-compatible host에서는 provider가 비거나 실제 backend와 다른 의미가 될 수 있다. 또한 비표준 usage, streaming chunk, tool/error response shape는 세부 attribute 누락 가능성이 있으므로 대표 호출로 검증해야 한다. [OpenAI instrumentor source](https://raw.githubusercontent.com/Arize-ai/openinference/main/python/instrumentation/openinference-instrumentation-openai/src/openinference/instrumentation/openai/__init__.py), [request wrapper source](https://raw.githubusercontent.com/Arize-ai/openinference/main/python/instrumentation/openinference-instrumentation-openai/src/openinference/instrumentation/openai/_request.py)

초기부터 LangChain과 OpenAI instrumentor를 동시에 켜면 동일 LLM 요청에 framework span과 SDK span이 중첩되어 노이즈가 커질 수 있다. 먼저 LangChain만 사용하고, provider-level 세부 정보가 실제로 부족할 때 OpenAI instrumentor를 별도 프로젝트/샘플 환경에서 비교한다. 이를 통제하려면 `auto_instrument=True`보다 명시적으로 `LangChainInstrumentor().instrument(tracer_provider=...)`를 호출하는 편이 예측 가능하다.

## 5. manual span이 필요한 지점

Phoenix OTEL은 `@tracer.agent`, `@tracer.chain`, `@tracer.tool` 및 `start_as_current_span(..., openinference_span_kind=...)`을 지원한다. [Tracing helpers](https://arize.com/docs/phoenix/tracing/how-to-tracing/setup-tracing/instrument)

우선순위는 다음과 같다.

1. `api/workflows/lg_orchestrator.py:164`의 `handle_message()`에 한 턴의 최상위 agent/chain span을 둔다.
2. `using_session()`으로 멀티턴을 묶되, 현재 `thread_id`는 raw user/channel ID이므로 가명화한 값을 사용한다. `using_user()`도 raw 사번/사용자 ID 대신 승인된 가명 ID만 사용한다. [Phoenix session/user metadata](https://arize.com/docs/phoenix/tracing/how-to-tracing/add-metadata/customize-spans)
3. `retrieve_start_chat_documents()`를 manual retriever span으로 감싸고 query 전문 대신 길이·hit count·source type 같은 안전한 속성을 우선 기록한다.
4. `execute_tool_call()`을 tool span으로 감싸 `tool_id`, success, latency만 기본 기록한다. tool arguments/results는 민감 정보 검토 후 허용한다.
5. HTTP webhook부터 worker까지 하나의 trace가 꼭 필요할 때만 W3C trace context를 Redis payload에 명시적으로 inject/extract한다. 현재 `CubeQueuedMessage`에는 context 필드가 없으므로 자동 연결되지 않는다.

## 6. self-hosted와 Phoenix Cloud

앱 측 공통 변수는 다음과 같다. `PHOENIX_BASE_URL`은 REST client용이고 trace exporter 설정은 `PHOENIX_COLLECTOR_ENDPOINT`를 사용한다. [Phoenix Python SDK](https://arize.com/docs/phoenix/sdk-api-reference)

- `PHOENIX_COLLECTOR_ENDPOINT`: Phoenix collector base/trace endpoint
- `PHOENIX_API_KEY`: 인증이 켜진 self-host 또는 Cloud API key
- `PHOENIX_PROJECT_NAME`: 환경별 project 이름
- 제안하는 앱 자체 flag: `PHOENIX_ENABLED=false` 기본값으로 fail-open 적용

self-host 기본 포트는 HTTP UI/OTLP `6006`(`/v1/traces`)와 gRPC `4317`이다. Phoenix Cloud는 HTTP trace collection만 지원하고, Settings에 표시되는 space별 hostname을 사용해야 한다. [Phoenix endpoint FAQ](https://arize.com/docs/phoenix/resources/frequently-asked-questions/what-is-my-phoenix-endpoint)

이 저장소는 사내 사용자 프로필과 연락처, 파일 URL을 다루므로 첫 production 후보는 **사내망 self-hosted Phoenix**가 적절하다. Phoenix 공식 문서는 self-hosted trace/eval/dataset 데이터가 자체 인프라 안에 남는다고 설명한다. SQLite는 로컬/단일 사용자에, PostgreSQL은 production/동시 사용에 권장된다. [Self-host privacy](https://arize.com/docs/phoenix/self-hosting/security/privacy), [self-host architecture](https://arize.com/docs/phoenix/self-hosting/architecture)

production에서는 versioned Docker image, persistent PostgreSQL, TLS/reverse proxy, `PHOENIX_ENABLE_AUTH=True`, 강한 `PHOENIX_SECRET`, system API key를 사용한다. self-host 인증은 기본 비활성이므로 내부망이라는 이유만으로 기본값을 유지하지 않는다. [Phoenix authentication](https://arize.com/docs/phoenix/self-hosting/features/authentication)

batch exporter가 production에 적합하지만 process 종료 전에 `shutdown()`/flush가 필요하다. uWSGI reload와 daemon 종료 시 flush hook을 검증하지 않으면 마지막 spans가 유실될 수 있다. [Phoenix OTEL setup](https://arize.com/docs/phoenix/tracing/how-to-tracing/setup-tracing/setup-using-phoenix-otel)

## 7. privacy/security 필수 조건

OpenInference hide 옵션의 기본값은 모두 `False`여서 입력, 출력, 메시지, tool 정의, invocation parameter가 기록될 수 있다. [Mask span attributes](https://arize.com/docs/phoenix/tracing/how-to-tracing/advanced/masking-span-attributes)

현재 실제 prompt에는 다음이 포함될 수 있다.

- profile summary와 conversation history (`api/workflows/start_chat/lg_graph.py:116-149`)
- 파일명과 file URL (`api/workflows/start_chat/lg_graph.py:86-104`)
- 사내 구성원 이름·부서·전화번호 (`api/workflows/start_chat/member_lookup/node.py:95-132`)
- 사용자 메시지 및 번역 원문

따라서 초기 production 설정은 최소한 아래를 기본으로 해야 한다.

```text
OPENINFERENCE_HIDE_INPUTS=true
OPENINFERENCE_HIDE_OUTPUTS=true
OPENINFERENCE_HIDE_LLM_TOOLS=true
PHOENIX_TELEMETRY_ENABLED=false
PHOENIX_ALLOW_EXTERNAL_RESOURCES=false   # air-gapped 환경
```

개발 환경에서 synthetic/non-sensitive 데이터로만 content visibility를 열고, 운영에서는 metadata allowlist와 가명 ID를 우선한다. Phoenix의 masking은 주로 coarse hide 옵션이므로, 특정 필드만 보고 싶다면 원문 자동 캡처를 끈 상태에서 redacted summary를 manual span attribute로 추가하는 편이 안전하다. retention은 기본 무기한이므로 `PHOENIX_DEFAULT_RETENTION_POLICY_DAYS`도 명시해야 한다. [Phoenix data retention](https://arize.com/docs/phoenix/settings/data-retention)

## 8. 최소 단계별 도입안

### Phase 0 — 로컬 PoC, application code 영향 없음

- 별도 Phoenix 18.0.0 container를 로컬에서 실행한다.
- synthetic Cube/workflow dev harness만 사용한다.
- 현재 dependency set을 기록하고 Phoenix 패키지 조합을 constraints로 고정한다.
- LangChain instrumentor가 `start_chat`, `translator`, interrupt/resume, structured fallback을 어떻게 표현하는지 확인한다.

### Phase 1 — trace-first MVP

- `arize-phoenix-otel`, `openinference-instrumentation-langchain`만 앱에 추가한다.
- feature flag를 기본 off로 두고 각 실제 프로세스에서 idempotent tracing init을 수행한다.
- `handle_message()` 안에 최상위 span과 가명 session ID, 환경/project metadata를 둔다.
- input/output masking을 기본 on으로 두고, exporter 장애가 chatbot 응답을 실패시키지 않는지 검증한다.
- 기존 JSONL과 `/monitor`는 그대로 유지한다.

### Phase 2 — 의미 있는 custom spans와 offline evals

- retriever, MCP/local tool, member lookup에 내용 비공개 manual spans를 추가한다.
- trace에서 확인된 failure mode를 dataset으로 만든다.
- deterministic eval: `ReplyIntent` schema/usable block, JSON fallback rate, tool success, translator action/slot correctness.
- 별도 judge가 필요한 eval: 답변 relevance, 번역 correctness/tone. Phoenix는 dataset/trace 평가와 experiment 비교를 지원한다. [Phoenix evaluations](https://arize.com/docs/phoenix/evaluation/evals)

### Phase 3 — 필요할 때만 확장

- OpenAI SDK instrumentor를 추가해 세부 token/tool attributes가 실제 custom endpoint에서 개선되는지 A/B 비교한다.
- webhook→Redis→worker 단일 trace가 운영상 필요할 때 queue context propagation을 설계한다.
- 지속 평가 경보/threshold trigger가 필요하면 Phoenix OSS 외부의 기존 alert stack 또는 Arize AX 등 별도 monitoring 계층을 평가한다.

## 최종 권고

**도입 권고: YES, 단 trace-first·self-hosted·masked PoC부터.**

가장 작은 유효 변경은 Phoenix 서버를 앱과 분리해 self-host하고, Cube worker에서 LangChain/LangGraph 계측 하나만 켜는 것이다. 이 구성만으로도 현재 흩어진 workflow/LLM 로그보다 실행 경로와 fallback/latency를 훨씬 쉽게 볼 수 있다. 반면 raw content 기본 캡처, 다중 프로세스 초기화, thread/Redis context 단절을 무시한 일괄 auto-instrumentation은 피해야 한다. 이 검토에서는 application code를 변경하지 않았다.
