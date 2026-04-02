# LangChain / LangGraph 개념 가이드

## 목적

이 문서는 아래 내용을 빠르게 이해하기 위한 입문 가이드다.

- LangChain이 무엇인지
- LangGraph가 무엇인지
- LangGraph에서 node가 어떻게 동작하는지
- 조건에 따라 다음 node를 다르게 보내는 branch를 어떻게 만드는지

이 저장소는 workflow 중심 구조를 지향하므로, LangGraph는 "대화나 업무를 여러 단계로 나눠 제어하는 방식"으로 이해하면 된다.

## 1. LangChain이란

LangChain은 LLM 애플리케이션을 만들 때 자주 필요한 부품을 묶어 주는 라이브러리다.

대표적으로 아래 요소를 다룬다.

- prompt template
- chat model 호출
- output parser
- tool binding
- retriever / RAG 구성
- runnable 체인 연결

즉 LangChain은 "LLM 한 번 호출"부터 "여러 컴포넌트를 연결한 파이프라인"까지 만들기 쉽게 해 주는 기반 레이어에 가깝다.

예를 들어 아래 같은 흐름은 LangChain으로 잘 표현된다.

```text
사용자 질문
-> prompt 구성
-> 모델 호출
-> 결과 파싱
-> 필요하면 tool 호출
-> 최종 응답 생성
```

## 2. LangGraph란

LangGraph는 LangChain 위에서 동작하는 graph orchestration 레이어다.

핵심 차이는 상태와 분기다.

- LangChain: 한 번의 체인 실행, 또는 비교적 선형적인 흐름에 강하다.
- LangGraph: 상태를 들고 여러 단계로 이동하고, 조건에 따라 다른 경로로 보내고, 중간에 반복하거나 멈추는 흐름에 강하다.

LangGraph는 아래 같은 상황에 특히 맞는다.

- 여러 step으로 이루어진 업무 workflow
- 슬롯 수집 후 부족한 정보 재질문
- tool 실행 결과에 따라 다음 단계 분기
- 사람 승인 전까지 대기
- agent loop처럼 반복 실행

간단히 말하면:

- LangChain은 부품과 실행 단위
- LangGraph는 그 부품을 상태 기반 workflow로 묶는 틀

## 3. LangGraph의 핵심 구성 요소

LangGraph를 이해할 때 중요한 것은 네 가지다.

- `State`: workflow가 현재까지 모은 데이터
- `Node`: state를 읽고 일부를 갱신하는 처리 함수
- `Edge`: 다음에 어느 node로 갈지 연결하는 선
- `Graph`: node와 edge를 묶은 전체 실행 구조

보통 아래처럼 생각하면 된다.

```text
state를 들고
-> node 하나 실행
-> state 일부 업데이트
-> edge 규칙으로 다음 node 선택
-> 종료할 때까지 반복
```

## 4. Node는 어떻게 동작하나

LangGraph의 node는 보통 "현재 state를 입력받아 state 변경분을 반환하는 함수"다.

가장 단순한 형태는 아래와 비슷하다.

```python
from typing import TypedDict


class ChatState(TypedDict, total=False):
    user_message: str
    intent: str
    answer: str


def classify_intent(state: ChatState) -> dict:
    message = state.get("user_message", "")

    if "재고" in message:
        return {"intent": "inventory"}
    return {"intent": "general"}
```

이 node는 아래처럼 동작한다.

1. 현재 `state`를 읽는다.
2. 필요한 판단이나 모델 호출을 수행한다.
3. 전체 state를 다시 만드는 대신, 바뀐 값만 dict로 반환한다.
4. LangGraph가 이 반환값을 기존 state에 합친다.

즉 node는 "현재 상태를 읽고 다음 단계에 필요한 변화만 기록하는 함수"라고 보면 된다.

## 5. 기본적인 graph 연결 예시

아래는 가장 단순한 LangGraph 예시다.

```python
from typing import TypedDict

from langgraph.graph import END, START, StateGraph


class ChatState(TypedDict, total=False):
    user_message: str
    intent: str
    answer: str


def classify_intent(state: ChatState) -> dict:
    message = state.get("user_message", "")
    if "재고" in message:
        return {"intent": "inventory"}
    return {"intent": "general"}


def answer_general(state: ChatState) -> dict:
    return {"answer": "일반 문의로 처리합니다."}


graph_builder = StateGraph(ChatState)
graph_builder.add_node("classify_intent", classify_intent)
graph_builder.add_node("answer_general", answer_general)

graph_builder.add_edge(START, "classify_intent")
graph_builder.add_edge("answer_general", END)

graph = graph_builder.compile()
```

위 예시는 아직 분기가 없어서 `classify_intent` 다음 경로가 정해져 있지 않다.
분기가 필요할 때는 conditional edge를 추가해야 한다.

## 6. 조건 분기는 어떻게 만드나

조건 분기의 핵심은 두 단계다.

1. 어떤 경로로 갈지 판단하는 routing 함수를 만든다.
2. `add_conditional_edges()`로 routing 결과와 다음 node를 연결한다.

가장 이해하기 쉬운 형태는 아래 예시다.

```python
from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph


class ChatState(TypedDict, total=False):
    user_message: str
    intent: str
    answer: str


def classify_intent(state: ChatState) -> dict:
    message = state.get("user_message", "")

    if "재고" in message:
        return {"intent": "inventory"}
    if "주문" in message:
        return {"intent": "order"}
    return {"intent": "general"}


def route_by_intent(state: ChatState) -> Literal["inventory_node", "order_node", "general_node"]:
    intent = state.get("intent", "general")

    if intent == "inventory":
        return "inventory_node"
    if intent == "order":
        return "order_node"
    return "general_node"


def inventory_node(state: ChatState) -> dict:
    return {"answer": "재고 조회 flow로 이동합니다."}


def order_node(state: ChatState) -> dict:
    return {"answer": "주문 처리 flow로 이동합니다."}


def general_node(state: ChatState) -> dict:
    return {"answer": "일반 상담 flow로 이동합니다."}


graph_builder = StateGraph(ChatState)

graph_builder.add_node("classify_intent", classify_intent)
graph_builder.add_node("inventory_node", inventory_node)
graph_builder.add_node("order_node", order_node)
graph_builder.add_node("general_node", general_node)

graph_builder.add_edge(START, "classify_intent")

graph_builder.add_conditional_edges(
    "classify_intent",
    route_by_intent,
    {
        "inventory_node": "inventory_node",
        "order_node": "order_node",
        "general_node": "general_node",
    },
)

graph_builder.add_edge("inventory_node", END)
graph_builder.add_edge("order_node", END)
graph_builder.add_edge("general_node", END)

graph = graph_builder.compile()
```

실행 흐름은 아래와 같다.

```text
START
-> classify_intent
-> route_by_intent
-> inventory_node / order_node / general_node 중 하나
-> END
```

## 7. 조건 분기에서 중요한 포인트

### 7.1 분기 판단은 state 기반으로 한다

라우팅 함수는 보통 node가 미리 state에 적어 둔 값을 읽는다.

예:

- intent 분류 결과
- tool 실행 성공 여부
- 필수 입력값 누락 여부
- 승인 여부
- 에러 여부

즉 "판단"과 "분기"를 한 함수에 다 몰아넣기보다,

- 앞 node에서 state에 판단 재료를 저장하고
- routing 함수가 그 값을 보고 다음 경로를 정하는 방식

으로 나누면 읽기 쉽고 테스트도 쉽다.

### 7.2 routing 함수는 부작용 없이 단순하게 유지한다

routing 함수 안에서 외부 API를 호출하거나 state를 복잡하게 바꾸기 시작하면 흐름이 꼬이기 쉽다.

권장 방식:

- node: 무거운 계산, 모델 호출, tool 호출, state 업데이트
- router: 다음 node 선택만 담당

### 7.3 branch key는 짧고 명확하게 정한다

예:

- `"need_more_info"`
- `"approved"`
- `"rejected"`
- `"retry"`
- `"done"`

이렇게 두면 graph를 시각화하거나 로그를 볼 때 의미를 바로 이해할 수 있다.

## 8. 실무에서 자주 쓰는 branch 패턴

### 8.1 정보 부족 시 재질문

```text
입력 분석
-> 필수 슬롯 충분함? yes -> 실행 node
-> 필수 슬롯 부족함? no -> 질문 node
```

이 패턴은 챗봇 workflow에서 가장 흔하다.

예:

- 날짜가 없으면 날짜를 다시 묻기
- 첨부파일이 없으면 업로드 요청하기
- 제품 코드가 없으면 코드 입력 요청하기

### 8.2 외부 API 결과 기반 분기

```text
조회 node
-> 성공 -> 결과 설명 node
-> 권한 없음 -> 권한 안내 node
-> 데이터 없음 -> 재입력 유도 node
-> 오류 -> 재시도 또는 fallback node
```

### 8.3 승인/취소 분기

```text
최종 확인 node
-> 승인 -> 제출 node
-> 수정 -> 입력 수집 node
-> 취소 -> 종료 node
```

## 9. 이 저장소 기준으로 이해하면 좋은 점

이 저장소는 이미 workflow, node, routing, state를 분리하는 구조를 지향한다.
그래서 LangGraph를 도입하면 개념 대응이 비교적 자연스럽다.

- `state.py`: LangGraph state 정의 위치
- `nodes.py`: LangGraph node 함수 위치
- `routing.py`: conditional branch 판단 함수 위치
- `graph.py`: `StateGraph` 구성 위치

즉 폴더 구조를 아래처럼 잡으면 읽기 쉽다.

```text
api/workflows/<workflow_id>/
  graph.py
  nodes.py
  routing.py
  state.py
```

이 구조의 장점은 다음과 같다.

- node 책임이 분리된다.
- 조건 분기 로직이 한곳에 모인다.
- 테스트 대상을 나누기 쉽다.
- workflow 시각화와 코드 구조가 잘 맞는다.

## 10. 최소 예시: 정보 부족 시 질문 branch

아래 예시는 업무형 챗봇에서 자주 나오는 패턴이다.

```python
from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph


class RequestState(TypedDict, total=False):
    user_message: str
    product_code: str
    status: str
    answer: str


def parse_request(state: RequestState) -> dict:
    message = state.get("user_message", "")

    if "ABC-123" in message:
        return {
            "product_code": "ABC-123",
            "status": "ready",
        }

    return {"status": "need_product_code"}


def route_after_parse(state: RequestState) -> Literal["ask_product_code", "run_lookup"]:
    if state.get("status") == "need_product_code":
        return "ask_product_code"
    return "run_lookup"


def ask_product_code(state: RequestState) -> dict:
    return {"answer": "조회할 제품 코드를 알려주세요."}


def run_lookup(state: RequestState) -> dict:
    code = state.get("product_code", "")
    return {"answer": f"{code} 기준 조회를 진행합니다."}


graph_builder = StateGraph(RequestState)
graph_builder.add_node("parse_request", parse_request)
graph_builder.add_node("ask_product_code", ask_product_code)
graph_builder.add_node("run_lookup", run_lookup)

graph_builder.add_edge(START, "parse_request")
graph_builder.add_conditional_edges(
    "parse_request",
    route_after_parse,
    {
        "ask_product_code": "ask_product_code",
        "run_lookup": "run_lookup",
    },
)
graph_builder.add_edge("ask_product_code", END)
graph_builder.add_edge("run_lookup", END)

graph = graph_builder.compile()
```

핵심은 아래 한 줄로 요약된다.

- node가 state를 보고 판단 재료를 기록한다.
- router가 그 기록을 보고 다음 node를 선택한다.

## 11. 정리

한 줄 요약은 아래와 같다.

- LangChain은 LLM 앱을 만들기 위한 부품과 실행 단위다.
- LangGraph는 그 부품을 상태 기반 graph workflow로 묶는 프레임워크다.
- node는 state를 읽고 변경분을 반환하는 처리 함수다.
- conditional branch는 `add_conditional_edges()`와 routing 함수로 만든다.

실무에서 중요한 습관도 같이 기억하면 좋다.

- state에는 다음 step에 필요한 정보만 저장한다.
- node와 routing 책임을 분리한다.
- branch key는 짧고 명확하게 정한다.
- 조건 분기는 사람 눈으로 읽히는 workflow가 되도록 설계한다.
