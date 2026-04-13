# Mongo Collections

이 문서는 현재 `llm_chatbot` 저장소가 MongoDB를 사용할 때 어떤 컬렉션을 무엇에 쓰는지 정리한다.  
특히 `cube_checkpoints`와 `cube_checkpoint_writes`가 둘 다 LangGraph 상태 저장에 쓰이기 때문에, 둘의 역할을 혼동하지 않도록 실제 코드 기준으로 설명한다.

## 1. 현재 사용하는 컬렉션

MongoDB 관련 기본 컬렉션 이름은 [api/config.py](/Users/daeyoung/Codes/llm_chatbot/api/config.py:44) 에서 정한다.

- `cube_conversation_history`
- `cube_checkpoints`
- `cube_checkpoint_writes`

세 컬렉션은 역할이 다르다.

| 컬렉션 | 주 용도 | 작성 주체 |
| --- | --- | --- |
| `cube_conversation_history` | 사용자/봇 대화 로그 보관 | `api/conversation_service.py` |
| `cube_checkpoints` | LangGraph thread의 스냅샷 저장 | `MongoDBSaver.put()` |
| `cube_checkpoint_writes` | 체크포인트에 연결된 중간 write / pending write 저장 | `MongoDBSaver.put_writes()` |

핵심 구분은 아래 한 줄로 정리할 수 있다.

- `cube_conversation_history`는 사람이 읽는 대화 로그다.
- `cube_checkpoints`와 `cube_checkpoint_writes`는 LangGraph 엔진이 resume 하기 위한 실행 상태다.

## 2. `cube_conversation_history`

### 2.1 역할

이 컬렉션은 앱 차원의 대화 이력 저장소다.

- 최근 대화 보기 화면
- 대화 문맥(history) 재주입
- 모니터링/감사성 조회

같은 용도로 사용된다.

실제 저장/조회 코드는 [api/conversation_service.py](/Users/daeyoung/Codes/llm_chatbot/api/conversation_service.py:73) 에 있다.

### 2.2 누가 쓰는가

- 저장: `append_message()`, `append_messages()`
- 조회: `get_history()`, `get_recent_messages()`
- 일반 대화 응답 생성 시 history 로딩: [api/workflows/start_chat/lg_graph.py](/Users/daeyoung/Codes/llm_chatbot/api/workflows/start_chat/lg_graph.py:104)

### 2.3 어떤 데이터가 들어가는가

문서 생성은 `_build_document()`를 통해 이루어진다. 저장 필드는 아래 성격을 가진다.

- `user_id`
- `conversation_id`
- `role`
- `content`
- `created_at`
- 선택 메타데이터
  예: `message_id`, `channel_id`

이 컬렉션은 "사용자와 봇이 무슨 말을 주고받았는가"를 보관한다.

### 2.4 무엇을 하지 않는가

이 컬렉션은 LangGraph resume 상태를 저장하지 않는다.

- 다음 노드가 어디인지
- interrupt 직전 상태가 무엇인지
- 어떤 task write가 남아 있는지

같은 정보는 여기 없다. 그런 정보는 `cube_checkpoints`, `cube_checkpoint_writes`에 저장된다.

## 3. `cube_checkpoints`

### 3.1 역할

이 컬렉션은 LangGraph thread의 메인 스냅샷 저장소다.

이 저장소가 있어야 같은 `thread_id`로 들어온 다음 요청에서 그래프가 이전 상태를 복원할 수 있다.  
이 저장은 [api/workflows/lg_orchestrator.py](/Users/daeyoung/Codes/llm_chatbot/api/workflows/lg_orchestrator.py:25) 에서 생성한 checkpointer가 담당한다.

`thread_id`는 [api/workflows/langgraph_checkpoint.py](/Users/daeyoung/Codes/llm_chatbot/api/workflows/langgraph_checkpoint.py:17) 기준으로 기본적으로 `user_id::channel_id` 형식이다.

즉, Cube 채널 대화 하나가 LangGraph 관점에서는 하나의 thread로 유지된다.

### 3.2 누가 쓰는가

이 컬렉션은 앱 코드가 직접 쓰지 않고, LangGraph의 `MongoDBSaver`가 쓴다.

- saver 생성: [api/workflows/langgraph_checkpoint.py](/Users/daeyoung/Codes/llm_chatbot/api/workflows/langgraph_checkpoint.py:54)
- 실제 저장 메서드: `MongoDBSaver.put()`

설치된 saver 구현은 아래 파일에 있다.

- [saver.py](/Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/langgraph/checkpoint/mongodb/saver.py:343)

### 3.3 어떤 데이터가 들어가는가

`put()` 기준으로 아래 성격의 데이터가 저장된다.

- `thread_id`
- `checkpoint_ns`
- `checkpoint_id`
- `parent_checkpoint_id`
- `type`
- `checkpoint`
- `metadata`
- `created_at` (`TTL` 활성 시)

여기서 중요한 필드는 아래다.

- `thread_id`
  어떤 대화 thread의 상태인지
- `checkpoint_id`
  해당 스냅샷의 버전 식별자
- `parent_checkpoint_id`
  바로 이전 스냅샷과의 연결
- `checkpoint`
  LangGraph가 serialize한 실제 상태 본문
- `metadata`
  step, source, writes 같은 실행 메타정보

### 3.4 무슨 일을 하는가

이 컬렉션은 "현재 그래프 상태의 기준 스냅샷"을 제공한다.

오케스트레이터가 같은 `thread_id`로 다시 들어오면:

1. LangGraph가 최신 checkpoint를 찾는다.
2. 그 시점의 상태를 복원한다.
3. interrupt 중이면 이어서 resume 한다.
4. 아니면 현재 입력으로 다음 실행을 시작한다.

즉, `cube_checkpoints`는 그래프가 어디까지 진행되었는지를 저장하는 메인 저장소다.

## 4. `cube_checkpoint_writes`

### 4.1 역할

이 컬렉션은 checkpoint에 연결된 중간 write, 즉 pending write 저장소다.

이름만 보면 모호해 보일 수 있지만, LangGraph 내부 용어와 동작에 맞춘 이름이다.  
실제로 `MongoDBSaver.get_tuple()`은 checkpoint를 읽은 뒤 이 컬렉션에서 관련 write를 다시 읽어 `pending_writes`로 복원한다.

관련 구현:

- 읽기: [saver.py](/Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/langgraph/checkpoint/mongodb/saver.py:214)
- 쓰기: [saver.py](/Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/site-packages/langgraph/checkpoint/mongodb/saver.py:390)

### 4.2 누가 쓰는가

이 컬렉션도 앱 코드가 직접 쓰지 않는다.

- LangGraph 런타임이 task 실행 중 생성한 write를 `MongoDBSaver.put_writes()`로 저장한다.

즉, 이 컬렉션은 "사용자 메시지"나 "최종 응답"을 저장하는 곳이 아니라, 그래프 실행 중간 산출물을 저장하는 곳이다.

### 4.3 어떤 데이터가 들어가는가

`put_writes()` 기준으로 아래 성격의 데이터가 저장된다.

- `thread_id`
- `checkpoint_ns`
- `checkpoint_id`
- `task_id`
- `task_path`
- `idx`
- `channel`
- `type`
- `value`
- `created_at` (`TTL` 활성 시)

특히 아래 필드가 중요하다.

- `task_id`
  어떤 task가 이 write를 만들었는지
- `task_path`
  어떤 실행 경로에서 생긴 write인지
- `channel`
  write의 종류
- `value`
  serialize된 실제 값

### 4.4 왜 별도 컬렉션이 필요한가

LangGraph는 checkpoint 본체 하나만 저장해서는 충분하지 않다.  
실행 중간에 task별 write를 따로 들고 있어야 다음과 같은 상황을 안정적으로 다룰 수 있다.

- interrupt 직전/직후 상태 복원
- resume 입력 반영
- task 스케줄링 정보 유지
- 에러 채널 정보 보관

LangGraph base 모듈에는 write용 특수 채널이 정의돼 있다.

- `__error__`
- `__scheduled__`
- `__interrupt__`
- `__resume__`

즉, `cube_checkpoint_writes`는 "체크포인트에 부속된 실행 이벤트/중간 write 저장소"라고 이해하는 편이 맞다.

### 4.5 무슨 일을 하는가

checkpoint 하나를 읽을 때 LangGraph는 이 컬렉션도 같이 읽는다.  
그 결과 checkpoint는 단순 스냅샷이 아니라, "재개 가능한 실행 상태"가 된다.

이 컬렉션이 없으면 아래 같은 resume 문맥이 약해진다.

- 사용자가 이전 interrupt 질문에 답했을 때
- 어떤 task가 대기 중이었는지
- 어떤 write가 아직 반영 대기 상태였는지

즉, `cube_checkpoints`가 메인 스냅샷이라면, `cube_checkpoint_writes`는 그 스냅샷에 붙는 보조 실행 상태다.

## 5. 한 턴이 저장되는 실제 흐름

현재 런타임 흐름은 아래와 같다.

1. Cube 메시지가 들어온다.
2. 워커가 [api/workflows/lg_orchestrator.py](/Users/daeyoung/Codes/llm_chatbot/api/workflows/lg_orchestrator.py:29) 의 `handle_message()`를 호출한다.
3. 오케스트레이터는 `user_id::channel_id`로 `thread_id`를 만든다.
4. LangGraph는 checkpointer를 통해 해당 thread의 최신 checkpoint를 읽는다.
5. 필요하면 `cube_checkpoint_writes`의 pending write도 같이 읽는다.
6. 그래프가 실행된다.
7. 새 checkpoint와 관련 write가 저장된다.
8. 별도로 사용자/봇 메시지는 `cube_conversation_history`에 저장된다.

즉, 한 턴 안에서도 저장 목적이 둘로 나뉜다.

- 사용자 관점 기록: `cube_conversation_history`
- 엔진 관점 실행 상태: `cube_checkpoints`, `cube_checkpoint_writes`

## 6. TTL과 보관 정책

기본 설정상 세 컬렉션의 보관 의도는 다르다.

- `cube_conversation_history`
  기본적으로 `CONVERSATION_TTL_SECONDS=0` 이라 TTL 없이 보관
- `cube_checkpoints`
  기본적으로 `CHECKPOINT_TTL_SECONDS=259200` 으로 3일 TTL
- `cube_checkpoint_writes`
  기본적으로 `CHECKPOINT_TTL_SECONDS=259200` 으로 3일 TTL

의도는 명확하다.

- 대화 이력은 더 오래 봐야 할 수 있다.
- LangGraph checkpoint 데이터는 resume용 단기 상태라 상대적으로 짧게 둬도 된다.

## 7. 운영 관점에서 기억할 점

- `cube_conversation_history`만 봐서는 LangGraph interrupt/resume 상태를 알 수 없다.
- `cube_checkpoints`만 봐서는 task별 pending write를 다 알 수 없다.
- resume 문제를 조사할 때는 `cube_checkpoints`와 `cube_checkpoint_writes`를 같이 봐야 한다.
- 사용자 대화 로그를 확인할 때는 `cube_conversation_history`를 봐야 한다.

## 8. 이름을 그대로 두는 이유

`cube_checkpoint_writes`는 처음 보면 다소 추상적으로 느껴질 수 있다.  
그래도 현재는 이름을 바꾸지 않고 유지한다.

이유는 아래와 같다.

- LangGraph saver의 내부 용어가 `writes`다.
- 코드와 문서가 LangGraph 개념과 직접 대응된다.
- 운영 중 컬렉션명 변경은 코드 수정이 아니라 데이터 마이그레이션 이슈까지 동반한다.

따라서 현재 저장소에서는 이름보다 문서 설명을 보강하는 쪽을 선택한다.
