# 워크플로 카탈로그 — 팀원용 사용 튜토리얼

> 최종 업데이트: 2026-04-28
> 대상 독자: 챗봇을 사용하거나 새 워크플로를 호출하려는 팀원
> 함께 보면 좋은 문서: [`workflow_build_with_langgraph.md`](./workflow_build_with_langgraph.md) (개발자용 핸드북)

> ⚠️ **최근 변경 (2026-04-28)** — MCP 패키지명이 `api/mcp/` → `api/mcp_client/`, `devtools/mcp/` → `devtools/mcp_client/` 로 바뀌었고 호환성 shim은 제거되었습니다. 이전 경로 import는 즉시 깨집니다. 워크플로/MCP 인프라 변경은 아래 "인프라 파일 소유권 정책" 섹션을 먼저 확인해 주십시오.

이 문서는 `api/workflows/` 안에서 **단독으로 동작 가능한 워크플로**가 무엇이고, 사용자가 어떤 발화를 보내야 각 워크플로가 트리거되는지를 정리합니다. 새 코드를 작성할 필요 없이 “어떤 메시지를 보내면 어떤 흐름이 도는가”만 알면 되는 사람을 위한 빠른 안내서입니다.

---

## 0. 큰 그림: 어떻게 단독으로 도나?

모든 메시지는 `start_chat` 루트 그래프로 들어옵니다. `start_chat`은 `classify_node`에서 사용자 메시지를 소문자로 정규화한 뒤, 등록된 각 워크플로의 `handoff_keywords` 중 하나라도 포함되면 해당 **서브그래프**로 분기합니다 (`api/workflows/start_chat/lg_graph.py:55`).

서브그래프로 일단 진입하면, 그 워크플로는 자기만의 노드/엣지/상태를 가지고 끝까지(또는 `interrupt`로 멈출 때까지) 단독 실행됩니다. 즉, **키워드가 맞으면 곧 “해당 워크플로가 단독으로 동작”** 한다고 보면 됩니다.

| Workflow ID | 단독 실행 트리거 키워드 | 위치 |
|---|---|---|
| `translator` | `translate`, `translation`, `번역`, `통역` | `api/workflows/translator/__init__.py:23` |
| `start_chat` | (트리거 없음 — 위 어느 키워드에도 해당하지 않으면 기본 진입 흐름) | `api/workflows/start_chat/lg_graph.py` |

> 매칭은 단순 substring 검사입니다. 예를 들어 “이거 한국어로 **번역**해줘”라는 메시지는 `translator`로 곧장 핸드오프됩니다. 일반 대화에서 우연히 키워드를 흘리면 의도치 않게 핸드오프될 수 있다는 점도 기억해 주세요.

---

## 1. `translator` — 번역

### 어떤 일을 하나
원문(`source_text`)과 목표 언어(`target_language`) 두 개의 슬롯을 채운 뒤, MCP `translate` 도구로 번역 결과와 한국어 발음을 반환합니다 (`api/workflows/translator/lg_graph.py:67`).

### 트리거 키워드
- `translate`, `translation`, `번역`, `통역`

### 흐름
```
resolve
  ├─ source_text 없음 → collect_source_text  (interrupt)
  ├─ target_language 없음 → collect_target_language  (interrupt)
  └─ 모두 있음 → translate → END
```
`resolve_node`가 슬롯 누락을 감지하면 `interrupt({"reply": ...})`로 멈추고, 다음 사용자 메시지에서 `Command(resume=...)`로 이어서 채웁니다.

### 예시 대화 (한 번에 다 주는 경우)
```
사용자: "Hello, how are you? 이거 일본어로 번역해줘"
봇    : (번역 결과 + 한국어 발음 표기)
```

### 예시 대화 (멀티턴)
```
사용자: "번역 좀 해줘"
봇    : "어떤 문장을 번역할까요?"
사용자: "내일 회의 언제로 옮길까요?"
봇    : "어떤 언어로 번역할까요?"
사용자: "영어"
봇    : (영어 번역 결과 + 한국어 발음)
```

---

## 2. `start_chat` — 일반 대화 (디폴트)

### 어떤 일을 하나
어떤 핸드오프 키워드에도 매칭되지 않은 모든 메시지를 처리합니다. `retrieve_context_node`가 RAG 컨텍스트와 사용자 업로드 파일 목록을 모아 LLM에 전달하고, 이전 대화 이력과 사용자 프로필도 함께 합쳐 응답을 생성합니다 (`api/workflows/start_chat/lg_graph.py:106`).

### 트리거
- 별도의 키워드 없음 — “기본 응답 경로”
- 단, 메시지에 위의 핸드오프 키워드가 섞여 있으면 다른 워크플로로 핸드오프됨

### 예시 대화
```
사용자: "어제 올렸던 분기 리포트 요약해줘"
봇    : (RAG + 업로드 파일 목록 + 사용자 프로필 기반 LLM 응답)
```

---

## 3. 운영 디렉터리 vs dev 디렉터리 구조

운영(`api/workflows/`)과 개발(`devtools/workflows/`)은 같은 “워크플로 패키지 계약”을 공유하지만, **루트에 들어가는 파일 종류가 다릅니다**. 새 워크플로를 dev에서 만들고 promote할 때 이 구분을 알고 있으면 import 에러나 “왜 dev에는 이 파일이 없지?”라는 혼란을 피할 수 있습니다.

> 🚧 **이 섹션은 현재 상태를 설명합니다 (legacy 패턴).** `HARNESS.md`의 "`api/` ↔ `devtools/` 격리 정책"에 따라 이 cross-import 의존 관계는 점진 정리 대상입니다. 새 코드에서는 dev가 `api.*`를 직접 import하지 않도록 하고, 마이그레이션 계획은 아래 §3.5를 참고하십시오.

### 핵심: dev 디렉터리는 “워크플로 패키지 컨테이너”일 뿐, 런타임 인프라가 아닙니다

- **`api/workflows/`** — 운영 런타임 인프라 + 운영 워크플로 패키지가 함께 들어 있습니다.
- **`devtools/workflows/`** — 개발 중인 워크플로 패키지만 들어 있습니다. 런타임 인프라는 옆 디렉터리(`devtools/workflow_runner/`)에 있고, 공유 코드는 (현재까지는) `api.workflows.*`에서 직접 import해 재사용해 왔습니다 — 이 부분이 위 격리 정책에서 정리 대상입니다.

### 역할 매핑표

| 역할 | `api/workflows/` (운영) | dev 환경 (재사용/대응 위치) |
|---|---|---|
| 워크플로 발견 | `registry.py` | 같은 `registry.py`를 재사용 (`discover_workflows(package_name="devtools.workflows")`) |
| 오케스트레이션 진입점 | `lg_orchestrator.py` (Cube 워커가 호출) | `devtools/workflow_runner/dev_orchestrator.py` (별도 위치) |
| 공유 상태 (`ChatState`) | `lg_state.py` | dev 패키지가 `from api.workflows.lg_state import ChatState`로 직접 import |
| 응답 모델 (`WorkflowReply`) | `models.py` | dev runner는 dict로 직접 반환 — 동일 모델 불필요 |
| 체크포인터 | `langgraph_checkpoint.py` (Mongo/Memory 분기) | dev runner는 항상 `MemorySaver` 직접 사용 |
| 의도 분류 유틸 | `intent_utils.py` | start_chat 그래프 자체를 dev runner에서 그대로 재사용 |
| 그래프 시각화 | `graph_visualizer.py` | dev 전용 도구라 런타임 코드와 무관 |

### 디렉터리 비교 (실제 트리)

```text
api/workflows/
├── __init__.py
├── registry.py
├── lg_orchestrator.py
├── lg_state.py
├── models.py
├── langgraph_checkpoint.py
├── intent_utils.py
├── graph_visualizer.py
├── start_chat/
└── translator/

devtools/workflows/
├── __init__.py
├── _template/
├── richinotification_test/
└── travel_planner_example/
    ├── __init__.py
    ├── constants.py
    ├── lg_graph.py
    ├── lg_state.py
    └── llm_decision.py
```

**왜 dev 쪽 루트에 `.py` 파일이 거의 없나** — 인프라가 prod 한 곳에만 살기 때문입니다. dev runner는 prod의 `discover_workflows()`를 그대로 호출해 dev 패키지를 찾고, dev 워크플로들은 `ChatState` 같은 공유 타입을 prod에서 가져옵니다. 인프라 코드를 두 곳에 두면 동기화 비용이 생기는데, 그 비용을 지우려고 일부러 한쪽으로 모아 둔 구조입니다.

### 그래서 promote는 어떻게 동작하나

`devtools/scripts/promote.py`는 leaf 패키지만 옮기면 끝납니다.

1. `devtools/workflows/<id>/` → `api/workflows/<id>/` 복사
2. `devtools/mcp_client/<id>.py` → `api/mcp_client/<id>.py` 복사
3. `devtools.mcp_client.` import를 `api.mcp_client.`로 치환 (인프라 import는 이미 `api.workflows.*`라 그대로 동작)
4. import 검증 후 dev 원본 삭제

운영 인프라는 처음부터 `api/`에 있고 dev에서도 같은 import 경로로 사용했기 때문에, promote 시 “인프라 파일을 옮긴다”는 단계가 아예 없습니다.

### 체크리스트 (legacy — 위 §3 도입부의 마이그레이션 안내 참조)

새 dev 워크플로를 만들 때 “루트에 `registry.py`가 없다, `lg_state.py`가 없다”는 이유로 인프라 파일을 dev 쪽에 새로 만들지 마세요. 항상 아래를 따릅니다 — 단, 아래 항목 중 `api.*` import 부분은 격리 정책에 따라 점진 폐기 대상입니다.

- 공유 상태가 필요하면 `from api.workflows.lg_state import ChatState` (격리 후에는 `devtools/` 자체 mirror 사본을 사용)
- 운영 워크플로의 불안정한 내부 helper를 dev 예제에서 직접 가져오지 말고, `ChatState`처럼 안정적인 공유 타입만 재사용합니다.
- 새 인프라 코드(라우팅 규칙, 새 체크포인터 등)는 `api/workflows/` 또는 `devtools/workflow_runner/` 중 적절한 곳에 두고, **`devtools/workflows/` 루트는 손대지 않음**

### 3.5 `api/` ↔ `devtools/` 격리 마이그레이션 (standalone but mirrored)

`HARNESS.md`의 격리 정책에 따라 두 영역을 `import`로 묶지 않습니다. 공유 개념은 양쪽에 mirror 사본으로 유지하고, Cube 송신처럼 dev에서 책임지지 않는 영역은 mirror 대신 dev 측에서 **삭제**합니다.

**핵심 원칙: devtools 워크플로는 Cube에 보내지 않습니다.** richnotification·multimessage·rich block 조립은 운영(`api/cube/`)의 책임이며, dev 워크플로는 평문 LLM 응답까지만 만듭니다. 이 원칙에 따라 cube 관련 cross-import는 mirror가 아니라 제거 대상입니다.

**진행 현황 (2026-04-28)**

| 단계 | 대상 | 처리 방식 | 상태 |
|---|---|---|---|
| 1 | `ChatState` (3 import) | mirror → `devtools/workflows/lg_state.py` | ✅ 완료 (`88d64ad`) |
| 2 | `richinotification_test/` 워크플로 (3 import: `api.cube.client/rich_blocks/payload`) | **삭제** (devtools는 Cube에 보내지 않음) | ✅ 완료 (`677305f`) |
| 3 | `is_stop_conversation_message` (1 import) | mirror → `devtools/workflows/intent_utils.py` | ✅ 완료 (`9810191`) |
| 4 | `devtools/workflow_runner/` 측 cross-import 5건 (`config`, `conversation_service` 3x, `discover_workflows`, lazy `start_chat.lg_graph`) | dev runner 자체 인프라 도입: `registry.py` + `conversation_history.py`. `start_chat` lazy import는 의도적 예외로 유지 (entry routing 점검용) | ✅ 완료 (`03945d1`) |
| 5 | `devtools/cube_message/samples.py`의 `api.cube.rich_blocks` (1 import) | 보류 — `cube_message`는 사무실에서 Cube 외형 점검용 매뉴얼 도구. 워크플로 격리 정책 직접 대상 아님 | ⏸ 영구 보류 |
| 6 | ruff 가드 (`pyproject.toml`의 `banned-module-level-imports = ["api"]` + `per-file-ignores`로 `devtools/workflows/`, `devtools/workflow_runner/`만 강제) | 정책 자동 강제 | ✅ 완료 (이번 커밋) |

**원칙 정리**

- mirror가 답인 경우: 양쪽이 동일 의미의 타입·로직을 공유하는 경우 (예: `ChatState`, `intent_utils`).
- 삭제가 답인 경우: dev가 그 기능을 담당하지 않는 경우 (예: Cube 송신 — 운영 책임).
- 보류가 답인 경우: 워크플로 런타임 바깥의 매뉴얼 도구 (예: `cube_message/`) — 별도 정책 결정 필요.

---

## ⚠️ 인프라 파일 소유권 정책 — 수정 전 Daeyoung에게 먼저 알려주세요

`api/workflows/` **루트의 인프라 파일들은 프로젝트 아키텍처를 정의하는 코어 레이어**입니다. 워크플로 패키지가 이 인프라 위에서 동작하도록 설계되어 있어, 인프라가 바뀌면 모든 워크플로가 영향을 받습니다. 따라서 아래 파일들은 **수정 전에 반드시 Daeyoung(owner)에게 먼저 알리고 함께 검토**해 주세요. 직접 PR을 올리거나 단독으로 수정하지 말아 주세요.

### 인프라 파일 목록 (수정 전 Daeyoung 통보 필수)

| 파일 | 역할 | 수정이 영향을 미치는 범위 |
|---|---|---|
| `api/workflows/registry.py` | 워크플로 자동 발견 + 정의 정규화 (`discover_workflows`, `get_workflow_definition` 계약) | 모든 워크플로의 등록/발견 동작 |
| `api/workflows/lg_orchestrator.py` | Cube 워커 진입점, 루트 그래프 컴파일·invoke·resume 처리 | 운영 트래픽 전체 |
| `api/workflows/lg_state.py` | 모든 워크플로가 상속하는 공통 `ChatState` | 전 워크플로의 상태 스키마 |
| `api/workflows/models.py` | `WorkflowReply` 등 오케스트레이터 ↔ Cube 응답 계약 | 응답 직렬화 / Cube 측 파서 |
| `api/workflows/langgraph_checkpoint.py` | 체크포인터 팩토리, `thread_id` 규칙, Mongo 컬렉션 검증 | 멀티턴 대화 지속성 / 데이터 저장 |
| `api/workflows/intent_utils.py` | 의도 분류 공통 유틸 | 핸드오프 라우팅 정확도 |
| `api/workflows/graph_visualizer.py` | LangGraph 시각화 도구 | 디버깅/문서 산출물 |
| `api/workflows/__init__.py` | 패키지 초기화 | 전 워크플로 import 경로 |
| `devtools/workflow_runner/dev_orchestrator.py` | dev 환경 오케스트레이터 (위 인프라와 짝) | dev runner 전체 |

### 자유롭게 수정해도 되는 영역 (통보 불필요)

- `api/workflows/<workflow_id>/` 안의 파일 — 본인이 담당하는 워크플로 패키지 내부
- `devtools/workflows/<workflow_id>/` 안의 dev 워크플로
- 워크플로 추가는 자동 발견 구조라 **인프라 파일을 건드릴 일이 없습니다**

### 통보 절차

1. 변경하려는 인프라 파일과 변경 사유를 정리
2. Daeyoung에게 사전 공유 (Slack/대면)
3. 함께 영향 범위 검토 후, Daeyoung이 직접 수정하거나 작업 위임 결정
4. 변경 후에는 운영 트래픽 영향이 있을 수 있으므로 배포 타이밍도 함께 조율

### 왜 이 정책이 있나

이 프로젝트의 워크플로 인프라는 Claude(아키텍트)가 일관된 설계 원칙으로 구축한 코어 레이어입니다. 부분 수정이 다른 영역의 가정을 깨면 디버깅이 매우 어렵고, 멀티턴 대화 지속성·체크포인터 호환성·자동 발견 계약 등 한눈에 보이지 않는 invariant가 많습니다. 워크플로 추가/수정은 패키지 안에서 충분히 가능하도록 설계되어 있으니, 인프라 변경이 정말 필요한 케이스인지부터 함께 검토하는 편이 안전합니다.

---

## 4. 자주 묻는 질문 (FAQ)

**Q. 한 메시지에 여러 워크플로의 키워드가 모두 들어 있으면?**
레지스트리 등록 순서대로 첫 번째로 매칭되는 워크플로가 선택됩니다 (`list_handoff_workflows()`는 `discover_workflows()`가 모듈을 알파벳 순으로 스캔합니다). 키워드 충돌이 잦다면 메시지를 나눠 보내는 편이 안전합니다.

**Q. 워크플로 도중에 빠져나오려면?**
`translator`는 LLM 결정 단계에서 종료 의도를 감지하면 `conversation_ended=True`로 빠져나옵니다. 사용자가 “취소”, “그만”, “종료” 같은 표현을 쓰면 됩니다.

**Q. 같은 사용자가 두 채널에서 동시에 다른 워크플로를 돌리면?**
`thread_id = user_id::channel_id` 규칙으로 체크포인터가 분리됩니다 (`api/workflows/langgraph_checkpoint.py:17`). 채널이 다르면 서로의 상태를 침범하지 않습니다.

**Q. 새 워크플로를 추가하려면?**
이 문서는 “이미 있는 것들”을 다룹니다. 만드는 절차는 [`workflow_build_with_langgraph.md`](./workflow_build_with_langgraph.md)의 5장(“새 워크플로를 만드는 표준 절차”)을 참고하세요.

---

## 5. 한 줄 요약

현재 단독 실행 가능한 업무 워크플로는 **`translator`** 하나이며, `handoff_keywords`를 사용자 메시지에 자연스럽게 포함시키는 것이 “단독 실행”의 트리거입니다. 키워드가 맞으면 해당 서브그래프가 멀티턴 `interrupt/resume` 패턴으로 끝까지 단독 진행됩니다.
