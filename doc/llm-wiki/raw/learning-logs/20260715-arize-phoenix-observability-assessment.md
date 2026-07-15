# Arize Phoenix observability 적용성 검토

- 조사일: 2026-07-15
- 범위: 현재 Flask + Redis Cube worker + LangGraph + `langchain-openai` 운영 경로와 `devtools/workflow_runner` 두 경로에 Phoenix OSS 적용 가능성 검토
- 결론: **코드/패키지 적합성은 PASS, 사내 배포 준비도는 CONDITIONAL PASS이다.** 운영과 devtools 모두 사용할 수 있지만 Phoenix server를 Flask/uWSGI 프로세스 안에 넣지 말고 별도 사내 서비스로 운영해야 한다. 사내 컨테이너, PostgreSQL, 저장소, 네트워크, TLS, 인증, 보안 승인 조건은 이 저장소만으로 확인할 수 없으므로 사내 PoC 전에 게이트 확인이 필요하다. 기존 JSONL/상태 모니터링은 유지하고 Phoenix는 trace 분석 계층으로 추가한다.

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

## 7. 사내 internal cloud 실행 판정

### 저장소에서 확인된 것

- 앱 런타임은 Python 3.11이고, 현재 LangChain/LangGraph 버전은 Phoenix/OpenInference 공식 선언 범위와 맞는다.
- 운영은 uWSGI Flask worker 2개와 Cube/scheduler daemon이 분리된 멀티프로세스 구조다(`wsgi.ini:12-19,41-45`).
- 실제 LLM 워크플로는 Cube daemon의 `api/workflows/lg_orchestrator.py:164-194`에서 실행된다. Flask worker만 계측하면 핵심 trace가 빈다.
- devtools는 port 5001의 독립 Flask runner이고 `devtools/workflow_runner/dev_orchestrator.py:144-234`에서 별도 graph를 stream한다. `api/`와 `devtools/`는 상호 import 금지이므로 계측 초기화도 각자 경로에 독립적으로 두어야 한다(`HARNESS.md:137-166`).
- `requirements.txt`에 Phoenix/OpenTelemetry 패키지가 없고, 저장소에 Phoenix 배포용 Docker/Compose/Helm manifest도 없다. 즉 소프트웨어적 적합성은 있지만 사내 배포가 준비된 상태는 아니다.

### 사내에서 반드시 확인할 게이트

| 게이트 | 통과 기준 | 통과하지 못하면 |
| --- | --- | --- |
| 실행 플랫폼 | version을 고정한 Phoenix container를 독립 service/pod로 실행 가능 | 운영 도입 불가; 개발자 local Phoenix만 가능 |
| 데이터베이스 | 공식 backend인 PostgreSQL 14+와 backup/restore를 준비하거나, PoC 범위를 단일 process·single-user persistent SQLite로 명시 | MongoDB 대체 불가; shared production 승인은 보류 |
| 앱→collector 네트워크 | Flask/Cube daemon host에서 internal OTLP HTTP endpoint(`/v1/traces`) 접근 가능 | trace export 불가 |
| 사용자→UI 네트워크 | 관리자/개발자가 사내 DNS + TLS reverse proxy를 통해 UI 접근 가능 | 운영 조사 효용 저하 |
| 인증/비밀 | auth, 강한 secret, system API key, 비밀 저장소, 키 교체 절차 가능 | prompt/trace UI 노출 위험 |
| 사내망 제약 | `PHOENIX_TELEMETRY_ENABLED=false`, 필요 시 `PHOENIX_ALLOW_EXTERNAL_RESOURCES=false`; OTLP Protobuf HTTP를 proxy가 차단하지 않음 | air-gapped/UI/export 오류 가능 |
| 데이터 승인 | prompt, profile, 연락처, 파일 URL에 대한 masking/retention/접근권 정책 승인 | raw content 수집 금지; metadata-only PoC만 가능 |
| 운영 안정성 | collector 장애 시 chatbot fail-open, uWSGI reload/daemon 종료 시 batch flush, 메모리/디스크 관측 가능 | 장애 감수가 되므로 production 활성화 보류 |

Phoenix 공식 운영 가이드는 resource 정액을 일괄 제시하지 않고 ingestion volume, attribute cardinality, retention에 맞춰 memory와 storage를 관측·조정하라고 권고한다. 따라서 사무실 PoC에서 1일 실제 trace 량과 span 크기를 재고 retention/storage를 산정해야 한다. [Phoenix production guide](https://arize.com/docs/phoenix/production-guide), [Docker deployment](https://arize.com/docs/phoenix/self-hosting/deployment-options/docker), [configuration and ports](https://arize.com/docs/phoenix/self-hosting/configuration)

## 8. production과 devtools 두 경로 적용법

### 권장 토폴로지

```text
Production Flask workers ----\
                              +--> Phoenix production service --> production PostgreSQL
Production Cube daemon ------/

Dev workflow runner ------------> Phoenix development service --> dev SQLite/PostgreSQL
```

Phoenix는 containerized web UI + OTLP collector + SQL backend로 구성된 앱이다. Flask 앱에 blueprint로 넣거나 uWSGI worker마다 Phoenix server를 띄우면 안 된다. 가장 안전한 구조는 **Phoenix server를 별도 internal cloud service로 배포**하고, 챗봇 프로세스에는 가벼운 OTLP exporter/instrumentor만 두는 것이다. [Phoenix architecture](https://arize.com/docs/phoenix/self-hosting/architecture)

### 현재 uWSGI의 세 번째 daemon으로 실행하는 방안

**기술적으로는 가능하지만, 단일 host·소규모 PoC용으로만 권장한다.** Phoenix는 `pip install arize-phoenix` 후 `phoenix serve`로 독립 long-running server를 실행하는 공식 CLI를 제공한다. 따라서 `wsgi.ini`의 Cube/scheduler와 같은 수준에 개념적으로 다음 daemon을 추가할 수 있다. [Phoenix terminal deployment](https://arize.com/docs/phoenix/self-hosting/deployment-options)

```ini
# 예시일 뿐이며, 실제 경로는 배포 환경에서 고정한 Phoenix 전용 venv로 변경
attach-daemon = /project/workSpace/phoenix-venv/bin/phoenix serve
```

이 방식은 다음 조건을 모두 만족할 때만 적합하다.

- internal cloud가 반드시 **단일 앱 instance**를 유지한다. 앱 instance가 수평 확장되면 각 host의 SQLite/Phoenix로 trace가 분산되고 port·저장소 일관성이 깨진다.
- `PHOENIX_WORKING_DIR`를 `/project/workSpace/...`와 같은 **재시작 후에도 남는 writable persistent volume**에 둔다. 기본 temporary SQLite 경로를 쓰면 재배포 시 trace가 사라질 수 있다.
- Phoenix server 패키지는 버전을 고정하고 가능하면 챗봇 venv와 분리한다. Phoenix 서버 의존성이 Flask 앱 의존성을 바꾸는 것을 피한다.
- Phoenix가 앱과 함께 restart되고 upgrade 시 DB migration도 시작되는 운영 결합을 수용한다. collector 정지는 챗봇 응답을 깨지 않도록 fail-open이어야 한다.
- port 6006(UI + OTLP HTTP) 또는 4317(OTLP gRPC)의 사내 접근·충돌·방화벽을 확인하고 Phoenix 프로세스의 health/log/disk 사용량을 별도로 감시한다.
- Phoenix 설정을 배포 플랫폼/비밀 저장소에서 **실제 OS environment**로 주입한다. 현재 `.env`는 `api/config.py:5-17`을 import하는 Python 프로세스에서만 `load_dotenv()`되므로, 독립 `phoenix` CLI가 자동으로 읽는다고 가정하면 안 된다.

### MongoDB를 Phoenix 저장소로 쓸 수 있나

**쓸 수 없다.** Phoenix OSS가 지원하는 database backend는 SQLite와 PostgreSQL 두 개다. 현재 `AFM_MONGO_URI`의 MongoDB는 챗봇 conversation history와 LangGraph checkpoint에 계속 사용하고, Phoenix trace/eval/dataset은 독립 SQLite 파일에 저장해야 한다. MongoDB를 PostgreSQL 대체제로 지정하는 adapter/config는 공식적으로 없다. [Phoenix storage architecture](https://arize.com/docs/phoenix/self-hosting/architecture), [Phoenix configuration](https://arize.com/docs/phoenix/self-hosting/configuration)

PostgreSQL이 없는 현재 조건에서는 **단일 Phoenix daemon + persistent SQLite + 짧은 retention**이 현실적인 사내 PoC 안이다. 다만 공식 문서는 SQLite를 local development/single-user에, PostgreSQL을 production/multi-user/HA에 권장한다. 여러 팀원이 동시 사용하거나 trace 량이 커지거나 app instance를 늘릴 예정이면 PostgreSQL 없이 운영 기준 PASS를 주면 안 된다. [Phoenix storage architecture](https://arize.com/docs/phoenix/self-hosting/architecture)

| 항목 | Production | Devtools |
| --- | --- | --- |
| Phoenix backend | 별도 사내 service + PostgreSQL | 개발자 local container + SQLite, 또는 공유 dev service |
| project | `llm-chatbot-prod` | `llm-chatbot-devtools-<developer>` |
| 자동 계측 | LangChain/LangGraph, 명시적으로 한 종류만 | 동일한 LangChain instrumentor |
| 내용 정책 | inputs/outputs/tools hide, 가명 session/user ID, metadata allowlist | synthetic/non-sensitive data에서만 선택적으로 content 표시 |
| exporter | batch, fail-open, shutdown flush | 빠른 확인을 위해 simple/batch 선택 가능 |
| 초기화 | Flask worker와 Cube daemon 각각 process-safe/idempotent init | `devtools.workflow_runner` 프로세스만 별도 init |
| 의미 | 실제 Cube→Redis→worker→LLM 경로 조사 | promote 전 graph/node/interrupt/resume 개발 피드백 |

### 하나의 Phoenix를 공유해도 되나

**기술적으로는 가능**하다. PoC나 소규모 팀은 하나의 internal Phoenix instance에 production/devtools project 이름을 분리해 전송할 수 있다. 그러나 Phoenix OSS의 한 instance는 single tenant이고 내부 데이터가 RBAC 역할에 따라 접근되므로 project 이름만으로는 완전한 환경 격리가 되지 않는다. 운영 prompt/PII와 개발 trace의 엄격한 격리가 필요하면 **production과 devtools에 독립 Phoenix instance + 독립 database**를 쓰는 것이 공식 권장과 맞다. [Phoenix architecture: tenancy and environment isolation](https://arize.com/docs/phoenix/self-hosting/architecture)

### devtools가 운영 검증을 대체하지는 않는다

devtools runner에 Phoenix를 붙이면 node 순서, latency, interrupt/resume, LLM/tool 호출을 개발 중에 빠르게 점검할 수 있다. 다만 devtools `start_chat`은 의도적으로 production의 RAG, profile, file, LLM 노드를 미러링하지 않고 Cube에도 전송하지 않는다(`HARNESS.md:168-184`). 따라서 devtools trace PASS는 workflow 개발 피드백이지 production end-to-end PASS가 아니다. 실제 사무실 검증은 Cube webhook, Redis queue, Cube daemon, custom LLM endpoint까지 포함해 별도로 해야 한다.

## 9. 제안하는 사무실 PoC 순서

1. Phoenix를 챗봇과 분리된 내부 container로 배포하고, 운영이 아닌 전용 Postgres/schema와 7일 retention을 준비한다.
2. auth/system API key, 사내 TLS/DNS, telemetry off, external resources off, inputs/outputs/tools hide를 먼저 적용한다.
3. devtools runner에서 synthetic workflow 20건을 전송해 graph node, interrupt/resume, LLM span을 확인한다.
4. production에서는 feature flag를 끄고 배포한 뒤 Cube daemon 한 프로세스에만 키고 metadata-only canary를 실행한다.
5. collector 정지/네트워크 timeout에서 챗봇 응답이 정상인지, uWSGI reload와 daemon 종료 시 flush가 되는지 검증한다.
6. 1일 ingestion 량, DB 증가량, 질의 latency, exporter CPU/memory, 소실 span 비율을 기록한다.
7. 보안·운영 승인 후 project/instance 격리 수준과 retention을 확정하고 점진적으로 활성화한다.

이 순서는 현재 보호된 파일인 `api/config.py`, `api/__init__.py`, `wsgi.ini`, `requirements.txt`, `api/workflows/lg_orchestrator.py`, `devtools/workflow_runner/dev_orchestrator.py`의 변경을 포함한다. 실제 구현 전에 변경 파일·새 설정 contract·테스트 계획을 먼저 제시하고 owner 승인을 받아야 한다.

## 10. privacy/security 필수 조건

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

## 11. 최소 단계별 도입안

### Phase 0 — local/devtools PoC

- 별도 Phoenix 18.0.0 container를 로컬에서 실행한다.
- synthetic/non-sensitive data로 `devtools/workflow_runner`를 사용한다.
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

가장 작은 유효 변경은 Phoenix 서버를 앱과 분리해 self-host하고, devtools에서 먼저 synthetic trace를 확인한 뒤 Cube worker에 LangChain/LangGraph 계측 하나만 켜는 것이다. 이 구성만으로도 현재 흩어진 workflow/LLM 로그보다 실행 경로와 fallback/latency를 훨씬 쉽게 볼 수 있다. 소규모 PoC는 하나의 Phoenix에 project를 분리해도 되지만, 운영 데이터 격리가 필요하면 운영/dev 인스턴스와 DB를 나눈다. 반면 raw content 기본 캡처, 다중 프로세스 초기화, thread/Redis context 단절을 무시한 일괄 auto-instrumentation은 피해야 한다. 이 검토에서는 application code를 변경하지 않았다.
