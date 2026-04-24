# Workflows

이 문서는 `llm_chatbot` 저장소에서 LangGraph 기반 워크플로가 실제로 어떻게 쓰이는지 설명한다.  
일반적인 LangGraph 소개보다, 현재 코드가 어떤 구조로 묶여 있고 앞으로 워크플로 수가 많아질 때 무엇을 유지하고 무엇을 바꿔야 하는지에 초점을 둔다.

## 1. 현재 런타임에서 워크플로가 도는 방식

현재 production 메시지 흐름의 핵심 경로는 아래와 같다.

1. Cube 입력이 `api/cube/router.py`로 들어온다.
2. 큐/워커를 거쳐 `api/workflows/lg_orchestrator.py`의 `handle_message()`가 호출된다.
3. 오케스트레이터는 `api/workflows/start_chat/lg_graph.py`의 루트 그래프를 한 번 컴파일해 재사용한다.
4. 루트 그래프는 먼저 `start_chat` 흐름을 돈다.
5. 일반 대화면 `retrieve_context -> generate_reply`로 끝난다.
6. 특정 업무 의도가 감지되면 `translator` 같은 서브그래프로 분기한다.
7. 서브그래프가 사용자 추가 입력이 필요하면 `interrupt()`로 멈추고, 다음 사용자 메시지가 오면 `Command(resume=...)`로 이어서 실행된다.

즉, 이 저장소는 “워크플로마다 독립 엔진을 여러 개 돌리는 구조”가 아니라, `start_chat`을 루트로 둔 하나의 LangGraph 런타임 안에 여러 업무용 서브그래프를 붙여 놓은 구조에 가깝다.

## 2. 이 저장소에서 LangGraph가 담당하는 개념

### 2.1 상태 머신

각 워크플로는 `StateGraph`로 정의된다.

- 루트 그래프: `api/workflows/start_chat/lg_graph.py`
- 서브그래프 예시:
  - `api/workflows/translator/lg_graph.py`

각 노드는 상태를 읽고 `dict`를 반환해 상태 일부를 갱신한다.  
즉, “함수 호출 순서”보다 “상태 전이 규칙”이 중심이다.

### 2.2 멀티턴 대화 유지

이 저장소에서 LangGraph를 쓰는 가장 큰 이유는 멀티턴 대화를 자연스럽게 이어가기 쉽기 때문이다.

- `interrupt({"reply": ...})`
  현재 턴에서 사용자에게 질문을 던지고 실행을 멈춘다.
- `Command(resume=user_input)`
  다음 사용자 입력으로 멈춘 지점부터 다시 이어간다.
- `checkpointer`
  중간 상태를 thread 단위로 저장한다.

이 패턴은 `translator`에서 가장 분명하다.
예를 들어 번역 워크플로는 원문이 없으면 먼저 원문을 묻고, 목표 언어가 없으면 다시 목표 언어를 묻는다. 이 흐름을 별도 세션 저장 코드를 많이 쓰지 않고 LangGraph의 interrupt/resume로 해결한다.

### 2.3 thread 단위 지속성

`api/workflows/langgraph_checkpoint.py`는 thread 식별과 체크포인터 생성을 담당한다.

- thread id: `user_id::channel_id`
- Mongo 설정이 있으면 `MongoDBSaver`
- 아니면 `MemorySaver`

중요한 점은, production에서는 워크플로별 thread를 따로 만들지 않고 “사용자 + 채널” 기준으로 하나의 대화 thread를 유지한다는 점이다.  
지금 구조에서는 루트 그래프가 하나이기 때문에 이 선택이 자연스럽다.

### 2.4 서브그래프 기반 handoff

`api/workflows/start_chat/lg_graph.py`는 레지스트리에서 handoff 가능한 워크플로를 읽어 서브그래프로 붙인다.

- 워크플로 발견: `api/workflows/registry.py`
- handoff 대상 조회: `list_handoff_workflows()`
- 루트 그래프 분기: `_route_after_classify()`

이 방식의 장점은 명확하다.

- 새 워크플로를 패키지 단위로 추가하기 쉽다.
- 루트 그래프가 하위 그래프의 내부 구현을 몰라도 된다.
- 테스트를 workflow 단위로 나눠 유지할 수 있다.

## 3. 워크플로 패키지의 실제 계약

현재 새 workflow 패키지가 production에 들어오려면 사실상 아래 계약을 맞춰야 한다.

### 3.1 패키지 메타데이터

각 워크플로는 `api/workflows/<workflow_id>/__init__.py`에서 `get_workflow_definition()` 또는 `WORKFLOW_DEFINITION`을 제공한다.

여기에는 보통 아래 정보가 들어간다.

- `workflow_id`
- `build_lg_graph`
- `state_cls`
- `handoff_keywords`
- `tool_tags` 선택 사항

레지스트리는 이 메타데이터만 보고 워크플로를 발견한다.

### 3.2 실제 LangGraph 구현

실행 그래프는 각 패키지의 `lg_graph.py`에서 만든다.

- 노드 함수 정의
- conditional edge 정의
- entry point 지정
- 필요 시 `interrupt()` 사용

테스트는 이 그래프를 `MemorySaver`로 컴파일해서 직접 검증한다.  
관련 예시는 `tests/test_translator_lg_graph.py`, `tests/test_start_chat_lg_graph.py`에 있다.

### 3.3 상태 정의는 지금 두 층으로 존재한다

현재 상태 정의는 약간 이중 구조다.

- LangGraph 런타임 상태: `api/workflows/lg_state.py`
  - `ChatState`, `StartChatState`, `TranslatorState` 같은 `TypedDict`
- 레지스트리/구버전 호환 상태: 각 workflow의 `state.py`
  - `WorkflowState` 기반 dataclass

즉, 실제 `StateGraph(...)`는 `TypedDict` 계열을 쓰는데, 워크플로 메타데이터에는 dataclass 기반 `state_cls`가 같이 남아 있다.  
문서를 읽지 않으면 왜 둘 다 있는지 헷갈리기 쉽다.

현재 코멘트상 `api/workflows/state_service.py`는 production LangGraph 경로에서는 직접 쓰지 않고 devtools 호환 때문에 남아 있다.  
유지 자체는 가능하지만, 새 팀원이 들어오면 “어느 상태가 진짜 런타임 상태인지”를 명확히 알려줘야 한다.

## 4. 워크플로별로 LangGraph가 어떻게 쓰이는가

### 4.1 `start_chat`: 루트 그래프

`start_chat`은 일반 대화와 업무형 워크플로 진입을 모두 맡는다.

- `entry_node`
  사용자 프로필을 1회 로딩한다.
- `classify_node`
  현재는 메시지의 키워드를 보고 어떤 workflow로 넘길지 결정한다.
- `retrieve_context_node`
  일반 질의응답이면 RAG 컨텍스트를 모은다.
- `generate_reply_node`
  대화 이력, 프로필, 파일 목록, 검색 컨텍스트를 합쳐 LLM 응답을 만든다.

핵심은 `start_chat`이 “모든 대화의 진입점 + 간단한 라우터” 역할을 동시에 한다는 점이다.

### 4.2 `translator`: interrupt/resume의 전형적인 예

`translator`는 LangGraph를 가장 잘 활용하는 예다.

- `resolve_node`가 현재 입력과 기존 상태를 바탕으로 다음 액션을 정한다.
- 원문이 없으면 `collect_source_text_node`에서 interrupt
- 목표 언어가 없으면 `collect_target_language_node`에서 interrupt
- 정보가 다 있으면 `translate_node`에서 도구 호출 후 종료

이 구조의 장점은 “누락 슬롯 수집”이 코드상 매우 명확하다는 점이다.  
챗봇 멀티턴 업무형 플로우는 대체로 이런 구조를 반복하게 되므로, 새 workflow를 만들 때 좋은 기준이 된다.

### 4.3 devtools 예제: 분기형 수집 플로우

production 워크플로에서는 제거되었지만, `devtools/workflows/travel_planner_example/`는 동료가 참고할 수 있는 self-contained multi-turn 예제로 남아 있다.

- 여행 스타일 수집
- 스타일 기반 목적지 추천
- 목적지 선택 대기
- 일정 수집
- 최종 계획 생성

여기서는 단순 선형 그래프보다 `resolve -> conditional routing` 패턴이 중요하다.  
정보가 일부만 들어와도 다음 노드를 다르게 선택할 수 있기 때문이다.

## 5. 이 구조가 지금은 왜 괜찮은가

현재 구조는 워크플로 수가 많지 않을 때 꽤 실용적이다.

- 진입점이 하나라서 운영 관점이 단순하다.
- 멀티턴 복원이 LangGraph 체크포인터로 통일된다.
- 워크플로 패키지를 디렉터리 단위로 추가할 수 있다.
- 각 workflow 테스트가 독립적이다.
- devtools 쪽에도 워크플로 러너와 템플릿이 있어 개발 경험이 나쁘지 않다.

특히 `devtools/scripts/new_workflow.py`와 `devtools/workflows/_template/`는 “새 그래프를 일관된 모양으로 시작하게 만든다”는 점에서 좋은 기반이다.

## 6. 워크플로가 많아지면 어디서부터 버거워지는가

여기서부터가 중요하다.  
현재 구조는 3~5개 정도의 업무형 워크플로에는 잘 맞지만, 수십 개로 늘어나면 아래 지점들이 병목이 된다.

### 6.1 키워드 기반 handoff는 충돌이 늘어난다

지금 `classify_node`는 `handoff_keywords` 포함 여부만 본다.

이 방식은 초반에는 빠르고 설명 가능하지만, workflow 수가 늘면 아래 문제가 생긴다.

- 키워드 중복
- 표현 다양성 증가
- 한국어/영어 혼합 발화 대응 한계
- 일반 대화와 업무형 발화의 경계 모호성

확장 시에는 최소한 아래 중 하나가 필요하다.

- workflow별 우선순위와 충돌 해결 규칙
- score 기반 router
- 소형 LLM 또는 분류 모델 기반 intent router
- 1차 coarse routing 후 2차 domain-specific routing

### 6.2 루트 그래프에 모든 서브그래프를 다 붙이는 방식은 비대해진다

현재 `start_chat` 빌더는 handoff 가능한 모든 workflow를 서브그래프로 컴파일한다.

워크플로가 많아지면 문제가 생긴다.

- 그래프 컴파일 시간이 길어진다.
- 메모리 사용량이 커진다.
- 루트 그래프 수정 없이도 사실상 전체 시스템 재컴파일이 필요해진다.
- 시각화와 디버깅 난도가 올라간다.

규모가 커지면 아래처럼 나누는 편이 낫다.

1. `start_chat`은 얇은 router graph로만 유지
2. 업무 도메인별 상위 그래프를 둠
   - 예: `language_root`, `travel_root`, `analytics_root`
3. 각 도메인 아래에서 세부 workflow를 다시 라우팅
4. 정말 무거운 그래프는 lazy compile 또는 별도 실행 경계로 분리

### 6.3 상태 스키마를 중앙에 계속 누적하면 관리가 어려워진다

지금은 `api/workflows/lg_state.py`에 여러 workflow 상태가 모여 있다.  
워크플로가 많아질수록 이 파일이 커지고, 필드 충돌과 의미 중복이 발생하기 쉽다.

확장 시 권장 방향은 아래와 같다.

- 공통 필드는 `BaseChatState`에만 둔다.
- workflow 고유 필드는 각 패키지 내부 상태 타입으로 분리한다.
- 루트 그래프와 서브그래프 사이에는 최소 공통 계약만 공유한다.

즉, 공유 상태는 줄이고 workflow별 로컬 상태는 늘리는 편이 낫다.

### 6.4 툴 등록이 전역 레지스트리에만 쌓이면 충돌 위험이 있다

예를 들어 `translator`는 `register_translator_tools()`에서 글로벌 MCP 레지스트리에 도구를 등록한다.

workflow 수가 늘면 아래를 조심해야 한다.

- `tool_id` 충돌
- 비슷한 기능의 도구가 여러 workflow에 중복 등록
- 테스트 간 전역 상태 오염

확장 시에는 다음이 필요하다.

- 명확한 네이밍 규칙
  - 예: `<workflow_id>.<tool_id>`
- workflow별 tool namespace
- 앱 시작 시 한 번만 등록하는 초기화 계층
- 테스트 fixture에서 전역 레지스트리 초기화 일관화

## 7. 워크플로 수가 많아질 때 추천하는 운영 원칙

실제로 scale-up 하려면 아래 원칙을 문서화해 두는 것이 좋다.

### 7.1 workflow package contract를 더 엄격히 고정

새 workflow는 최소한 아래 파일을 가지게 하는 편이 낫다.

- `__init__.py`
- `lg_graph.py`
- `state.py` 또는 `lg_state.py`
- `nodes.py`
- `prompts.py` 선택
- `tools.py` 선택
- `README.md` 또는 설명 문서 선택
- `tests/test_<workflow_id>_lg_graph.py`

지금 일부 workflow는 `nodes.py`가 있고 일부는 `lg_graph.py` 하나에 몰려 있다.  
개수가 많아지면 구조 편차가 디버깅 비용으로 돌아온다.

### 7.2 resolve node 패턴을 표준화

현재 `translator`와 `devtools/workflows/travel_planner_example/`는 사실상 같은 패턴을 공유한다.

- 입력 해석
- 누락 정보 판별
- stop/cancel 판별
- 다음 노드 선택

이 공통 패턴을 추상화하면 새 workflow 추가 속도가 빨라진다.  
예를 들어 “slot-filling workflow base pattern” 같은 내부 가이드를 만들어도 좋다.

### 7.3 interrupt payload 형식을 통일

지금은 대부분 `{"reply": ...}` 형태를 쓴다.  
규모가 커지면 여기에 아래 필드도 함께 넣는 것이 좋다.

- `reply`
- `expected_input`
- `missing_slot`
- `workflow_id`
- `examples`

그러면 UI, 로그, 테스트, devtools runner가 모두 같은 계약을 사용할 수 있다.

### 7.4 테스트를 그래프 단위와 오케스트레이터 단위로 분리

현재도 어느 정도 그렇게 되어 있지만, 많아질수록 구분이 더 중요하다.

- 그래프 단위 테스트
  - node/edge/interrupt 동작 검증
- 오케스트레이터 단위 테스트
  - 루트 진입, handoff, resume, reply extraction 검증
- 회귀 테스트
  - 키워드 충돌
  - stop/cancel 처리
  - checkpoint 복원

## 8. 문서에 남겨둘 만한 개선 포인트

아래는 당장 코드를 뜯어고쳐야 한다는 뜻은 아니고, 유지보수 관점에서 문서화해 둘 가치가 있는 항목이다.

### 8.1 `start_chat`이 핵심 그래프인데 레지스트리/시각화 목록에는 없다

`start_chat`은 루트 그래프이지만 `api/workflows/start_chat/__init__.py` 코멘트대로 레지스트리에 등록하지 않는다.  
그래서 `/workflows` 페이지에서 보이는 목록은 handoff 대상 워크플로 위주이고, 실제 메인 그래프인 `start_chat`은 빠진다.

이건 새 팀원이 시스템을 이해할 때 꽤 헷갈릴 수 있다.  
문서에서 분명히 설명하거나, 시각화 전용 엔트리로라도 노출하는 편이 낫다.

### 8.2 런타임 상태 타입과 레지스트리 상태 타입이 분리되어 있다

현재는 `TypedDict` 기반 LangGraph 상태와 dataclass 기반 `WorkflowState`가 함께 존재한다.  
devtools/legacy 호환 때문에 유지되는 것으로 보이지만, 장기적으로는 아래 중 하나로 정리하는 편이 낫다.

- 완전히 분리된 역할을 문서로 고정
- devtools도 LangGraph 상태 타입 기준으로 맞춤
- 더 이상 필요 없는 레이어 정리

### 8.3 `_compiled_graph` 단일 캐시는 단순하지만 동적 변경에는 약하다

`api/workflows/lg_orchestrator.py`는 루트 그래프를 한 번만 컴파일해 캐시한다.

장점:

- 빠르다
- 단순하다

주의점:

- 새 workflow 추가나 handoff metadata 변경이 있으면 보통 프로세스 재시작이 필요하다
- 런타임 중 registry reload를 기대하면 안 된다

운영 모델이 “배포 시 재시작”이라면 충분히 괜찮지만, hot-reload 성격을 기대하면 별도 설계가 필요하다.

## 9. 새 workflow를 추가할 때 권장 체크리스트

1. 이 workflow가 정말 루트 그래프의 handoff 대상이어야 하는지 먼저 결정한다.
2. `handoff_keywords`만으로 안정적으로 라우팅 가능한지 검토한다.
3. 멀티턴이라면 `interrupt()/resume` 지점을 먼저 설계한다.
4. 공통 상태에 넣을 필드와 로컬 상태에 둘 필드를 분리한다.
5. 도구가 필요하면 `tool_id` 네이밍 충돌을 먼저 확인한다.
6. 최소한 그래프 단위 테스트와 루트 handoff 테스트를 같이 추가한다.
7. `/workflows` 시각화에서 설명 가능한 수준으로 노드 이름을 정한다.

## 10. 한 줄 요약

이 저장소의 LangGraph 구조는 현재 “`start_chat` 루트 그래프 + 업무별 서브그래프 + checkpoint 기반 interrupt/resume” 모델이다.  
지금 규모에서는 단순하고 실용적이지만, workflow가 많아질수록 라우팅 전략, 상태 경계, 그래프 컴파일 단위, 전역 tool registry를 더 엄격하게 분리해야 유지보수가 쉬워진다.
