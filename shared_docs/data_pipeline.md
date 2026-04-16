# 데이터 파이프라인 가이드

이 문서는 사용자의 메시지가 들어온 뒤 어떤 경로를 거쳐 응답이 생성되고, 어떤 저장소에 무엇이 남는지 설명합니다.
원문 기준은 `doc/mongo_collections.md`, `doc/project_structure.md`, `doc/code_explain/workflows.md`이며, 현재 코드 구조에 맞게 합쳐 정리했습니다.

## 1. 전체 흐름

```text
Cube 요청
  -> api/cube/router.py
  -> api/cube/service.accept_cube_message()
  -> api/cube/queue.py
  -> api/cube/worker.py
  -> api/cube/service.process_incoming_message()
  -> api/workflows/lg_orchestrator.py
  -> api/workflows/start_chat 또는 서브워크플로
  -> api/cube/client.py
  -> Cube 응답 전송
```

핵심은 HTTP 수신과 실제 LLM 처리를 큐로 분리해 두었다는 점입니다.

## 2. 요청 수신과 큐 적재

Cube는 `/api/v1/cube/receiver`로 메시지를 보냅니다.
`api/cube/router.py`는 요청 JSON을 받아 `accept_cube_message()`로 넘기고, 이 함수는 먼저 메시지를 큐에 적재합니다.

이 단계의 특징:

- 빈 메시지나 wake-up 이벤트는 워크플로로 넘기지 않고 무시합니다.
- 정상 메시지는 `enqueue_incoming_message()`를 통해 큐에 적재합니다.
- 큐 적재 성공 여부에 따라 `accepted`, `duplicate`, `ignored` 상태를 반환합니다.
- 이 구조 덕분에 HTTP 응답 시간과 실제 워크플로 처리 시간을 분리할 수 있습니다.

## 3. 워커 소비와 재시도

`cube_worker.py` 또는 `api/cube/worker.py`가 큐에서 메시지를 하나씩 가져옵니다.

워커 단계의 특징:

- `dequeue_queued_message()`로 메시지를 가져옵니다.
- 처리 실패 시 재시도 횟수를 관리합니다.
- 최대 재시도 전이면 requeue 합니다.
- 최대 재시도에 도달하면 acknowledge 후 실패 로그를 남깁니다.
- 성공 시 큐에서 acknowledge 처리합니다.

즉, 큐 워커는 “비동기 처리 + 재시도 제어”를 맡습니다.

## 4. 사용자 입력 저장

`api/cube/service.py`의 `process_incoming_message()`는 워크플로 실행 전에 사용자 발화를 대화 이력 저장소에 남깁니다.

저장 메타데이터에는 아래 값이 포함될 수 있습니다.

- `channel_id`
- `message_id`
- `direction`
- `source`
- `user_name`

이 단계가 먼저 수행되기 때문에 이후 응답 생성 실패가 발생해도 입력 이력 자체는 남길 수 있습니다.

## 5. 워크플로 실행

실제 LangGraph 진입점은 `api/workflows/lg_orchestrator.py`의 `handle_message()`입니다.

오케스트레이터는 아래 순서로 동작합니다.

1. `user_id::channel_id` 형식으로 `thread_id`를 생성합니다.
2. checkpointer를 붙인 루트 그래프를 가져옵니다.
3. 현재 thread 상태를 확인합니다.
4. 이미 interrupt 상태가 있으면 `Command(resume=...)`로 재개합니다.
5. interrupt 상태가 없으면 `start_chat` 그래프에 새 입력을 넣어 실행합니다.
6. 실행 후 마지막 상태에서 reply와 `workflow_id`를 꺼냅니다.

즉, 같은 사용자와 같은 채널의 후속 메시지는 같은 LangGraph thread를 이어서 사용합니다.

## 6. 루트 그래프와 서브워크플로

`api/workflows/start_chat/lg_graph.py`가 기본 루트 그래프입니다.

이 그래프는 두 역할을 함께 합니다.

- 일반 대화 처리
- 업무형 서브워크플로 handoff

현재 흐름은 아래와 같습니다.

1. `entry_node`가 프로필을 1회 로딩합니다.
2. `classify_node`가 사용자 메시지와 `handoff_keywords`를 비교합니다.
3. 일반 대화면 `retrieve_context -> generate_reply` 경로로 갑니다.
4. 특정 업무 키워드가 감지되면 `translator`, `travel_planner`, `chart_maker` 같은 서브그래프로 분기합니다.

이 구조 때문에 이 저장소는 “여러 워크플로 엔진 병렬 운용”보다 “하나의 루트 그래프 아래 여러 서브그래프를 붙인 모델”로 이해하는 편이 정확합니다.

## 7. 컨텍스트 수집과 응답 생성

일반 대화 경로에서는 `retrieve_context_node()`가 검색 컨텍스트를 모으고, `generate_reply_node()`가 최종 응답을 만듭니다.

응답 생성 시 조합되는 입력:

- 대화 이력
- 검색 컨텍스트
- 사용자 프로필
- 파일 전달 시스템의 사용자 파일 목록

즉, 일반 대화는 단순 LLM 호출이 아니라 history, RAG, profile, file metadata를 합쳐 프롬프트를 구성합니다.

## 8. 멀티턴과 interrupt/resume

업무형 워크플로는 필요한 정보가 부족하면 `interrupt()`로 사용자 입력을 다시 요청합니다.

예:

- 번역 워크플로
  원문이 없으면 원문을 묻고, 목표 언어가 없으면 다시 목표 언어를 묻습니다.
- 여행 계획 워크플로
  여행 스타일, 목적지, 일정 등 누락 슬롯을 순서대로 수집합니다.

다음 사용자 메시지가 들어오면 오케스트레이터가 같은 `thread_id`의 상태를 읽고 `resume`으로 이어서 실행합니다.

이때 대화 이력 저장과 LangGraph 실행 상태 저장은 서로 다른 저장소를 사용합니다.

## 9. Mongo 저장소 구분

MongoDB를 사용할 때 현재 저장소는 기본적으로 아래 세 컬렉션을 씁니다.

- `cube_conversation_history`
- `cube_checkpoints`
- `cube_checkpoint_writes`

세 컬렉션의 역할은 다릅니다.

| 컬렉션 | 주 용도 | 작성 주체 |
| --- | --- | --- |
| `cube_conversation_history` | 사용자와 봇의 대화 로그 보관 | `api/conversation_service.py` |
| `cube_checkpoints` | LangGraph thread의 스냅샷 저장 | `MongoDBSaver.put()` |
| `cube_checkpoint_writes` | 체크포인트에 연결된 중간 write, pending write 저장 | `MongoDBSaver.put_writes()` |

핵심 구분:

- `cube_conversation_history`는 사람이 읽는 대화 로그입니다.
- `cube_checkpoints`와 `cube_checkpoint_writes`는 LangGraph 엔진이 resume 하기 위한 실행 상태입니다.

## 10. `cube_conversation_history`

이 컬렉션은 앱 차원의 대화 이력 저장소입니다.

주요 용도:

- 최근 대화 보기 화면
- 대화 문맥 재주입
- 모니터링과 감사성 조회

일반적으로 저장되는 성격의 필드:

- `user_id`
- `conversation_id`
- `role`
- `content`
- `created_at`
- 선택 메타데이터
  예: `message_id`, `channel_id`, `direction`, `source`, `workflow_id`

중요한 점:

- 이 컬렉션은 LangGraph resume 상태를 저장하지 않습니다.
- 다음 노드 위치나 interrupt 직전 상태는 여기에 없습니다.

## 11. `cube_checkpoints`

이 컬렉션은 LangGraph thread의 메인 스냅샷 저장소입니다.

역할:

- 같은 `thread_id`로 들어온 다음 요청에서 이전 상태를 복원합니다.
- 그래프가 어디까지 진행되었는지의 기준 스냅샷을 보관합니다.

대표 필드 성격:

- `thread_id`
- `checkpoint_ns`
- `checkpoint_id`
- `parent_checkpoint_id`
- `checkpoint`
- `metadata`
- `created_at`

즉, `cube_checkpoints`는 “현재 그래프 상태의 기준 스냅샷”입니다.

## 12. `cube_checkpoint_writes`

이 컬렉션은 checkpoint에 연결된 중간 write, 즉 pending write 저장소입니다.

역할:

- interrupt 직전과 직후 상태 복원
- resume 입력 반영
- task 스케줄링 정보 유지
- error, interrupt, resume 관련 특수 채널 보관

대표 필드 성격:

- `thread_id`
- `checkpoint_ns`
- `checkpoint_id`
- `task_id`
- `task_path`
- `idx`
- `channel`
- `type`
- `value`
- `created_at`

즉, `cube_checkpoints`가 메인 스냅샷이라면 `cube_checkpoint_writes`는 그 스냅샷에 붙는 보조 실행 상태입니다.

## 13. 한 턴에서 무엇이 어디에 저장되는가

메시지 한 턴은 저장 목적이 둘로 나뉩니다.

### 사용자 관점 기록

- 사용자 입력
- 봇 응답
- 조회와 모니터링용 메타데이터

이 정보는 `cube_conversation_history`에 남습니다.

### 엔진 관점 실행 상태

- 현재 thread 스냅샷
- interrupt 직전 상태
- pending write
- resume 관련 내부 상태

이 정보는 `cube_checkpoints`, `cube_checkpoint_writes`에 남습니다.

따라서 resume 문제를 조사할 때는 대화 이력만 보면 안 되고, checkpoint 계열 컬렉션을 같이 봐야 합니다.

## 14. 응답 전송과 출력 저장

워크플로가 반환한 텍스트는 `plan_delivery()`를 거쳐 전송 단위로 분할될 수 있습니다.

- 일반 텍스트는 `send_multimessage()`로 전송합니다.
- 리치 알림이 필요하면 `send_richnotification()`으로 전송합니다.

응답 전송 후 assistant 메시지도 다시 대화 이력 저장소에 기록합니다.
이때 `reply_to_message_id`, `workflow_id` 같은 메타데이터를 함께 남길 수 있습니다.

중요한 점:

- 응답은 이미 사용자에게 전달된 뒤 저장되므로, 출력 저장 실패는 다시 사용자 오류로 올리지 않습니다.

## 15. TTL과 보관 정책

기본 설정상 세 컬렉션의 보관 의도는 다릅니다.

- `cube_conversation_history`
  기본적으로 TTL 없이 오래 보관하는 용도입니다.
- `cube_checkpoints`
  resume용 단기 상태라 상대적으로 짧은 TTL을 둘 수 있습니다.
- `cube_checkpoint_writes`
  checkpoint와 같은 TTL 정책을 따릅니다.

즉, 대화 이력은 더 길게 보고, LangGraph 실행 상태는 짧게 보관하는 의도가 기본입니다.

## 16. 운영 관점에서 기억할 점

- `cube_conversation_history`만 봐서는 LangGraph interrupt/resume 상태를 알 수 없습니다.
- `cube_checkpoints`만 봐서는 task별 pending write를 다 알 수 없습니다.
- resume 문제를 조사할 때는 `cube_checkpoints`와 `cube_checkpoint_writes`를 같이 봐야 합니다.
- 사용자 대화 로그를 확인할 때는 `cube_conversation_history`를 봐야 합니다.

## 17. 한 줄 요약

이 저장소의 데이터 파이프라인은 “Cube 입력을 큐로 분리해 워커가 처리하고, LangGraph가 thread 단위로 상태를 이어가며, 사람용 대화 로그와 엔진용 실행 상태를 서로 다른 저장소에 남기는 구조”입니다.
