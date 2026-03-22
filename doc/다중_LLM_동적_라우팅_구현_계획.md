# 다중 LLM 동적 라우팅 구현 계획

## 1. 목적

현재 서비스는 단일 `LLM_MODEL`만 사용한다. 앞으로는 아래 두 요구를 동시에 만족해야 한다.

- 사용자가 특정 모델을 직접 선택할 수 있어야 한다.
- 동시 사용자가 많아질 때 운영 정책에 따라 더 적합한 모델로 자동 분산할 수 있어야 한다.

대상 후보 모델은 아래와 같다.

- `gpt-oss-120b`
- `gpt-oss-20b`
- `Kimi-K2.5`
- `GLM-4.7`
- `HCP-LLM-Latest`
- `Qwen3-Next-80B-A3B-Instruct`

이 문서는 현재 코드 구조를 기준으로, 위험을 낮추면서 다중 모델 동적 선택 기능을 도입하는 구현 계획을 정리한다.

---

## 2. 현재 구조 진단

현재 코드 기준으로 LLM 호출 경로는 매우 단순하다.

- [api/config.py](/Users/daeyoung/Codes/llm_chatbot/api/config.py)에서 `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` 단일 설정을 읽는다.
- [api/llm/service.py](/Users/daeyoung/Codes/llm_chatbot/api/llm/service.py)의 `generate_reply()`가 항상 같은 모델로 `/chat/completions`를 호출한다.
- [api/cube/service.py](/Users/daeyoung/Codes/llm_chatbot/api/cube/service.py)는 사용자 메시지를 큐에 넣고, worker가 나중에 LLM을 호출한다.
- [api/cube/models.py](/Users/daeyoung/Codes/llm_chatbot/api/cube/models.py)의 `CubeIncomingMessage`와 `CubeQueuedMessage`에는 모델 관련 메타데이터가 없다.
- [api/cube/queue.py](/Users/daeyoung/Codes/llm_chatbot/api/cube/queue.py)는 큐 적재/재시도만 제공하고, 현재 큐 길이 조회 유틸리티는 없다.
- [api/conversation_service.py](/Users/daeyoung/Codes/llm_chatbot/api/conversation_service.py)는 현재 MongoDB 우선, 실패 시 In-Memory 폴백 구조이며, 사용자별 모델 선호도 저장 기능은 없다.

즉, 지금 상태에서 바로 "사용자 선택"과 "부하 기반 자동 전환"을 동시에 넣으려면 아래 공백을 먼저 메워야 한다.

- 모델 목록과 정책을 관리할 레지스트리
- 요청 모델과 실제 선택 모델을 구분하는 resolver
- 큐를 통과해도 사라지지 않는 모델 선택 메타데이터
- 사용자 선호 모델 저장소
- 부하 판단용 큐 길이/상태 조회
- 모델별 fallback 정책

---

## 3. 설계 원칙

이번 기능은 아래 원칙으로 구현하는 것이 안전하다.

### 3.1 기본 동작은 유지한다

초기 배포에서는 기존과 동일하게 기본 모델 1개만 사용해도 동작해야 한다. 다중 모델 설정이 없으면 현재 단일 모델 구조처럼 동작해야 한다.

### 3.2 사용자 요청 모델과 실제 실행 모델을 분리한다

사용자가 `GLM-4.7`을 요청했더라도, 비활성 상태거나 운영 정책상 허용되지 않으면 실제 호출 모델은 달라질 수 있다. 따라서 아래 두 값은 분리해야 한다.

- `requested_model`: 사용자가 직접 요청한 모델 또는 저장된 선호 모델
- `resolved_model`: resolver가 실제 호출하기로 결정한 모델

### 3.3 비동기 큐를 고려해 모델 의도를 보존한다

현재 Cube 요청은 큐에 적재된 뒤 worker가 비동기로 처리한다. 따라서 사용자가 명시한 모델 선택은 enqueue 시점에 payload에 포함되어야 한다. 그렇지 않으면 worker 시점에 요청 의도가 사라진다.

### 3.4 자동 라우팅은 worker에서 결정한다

부하 기반 자동 선택은 큐 길이, 처리 중 메시지 수, 모델별 장애 상태를 봐야 의미가 있다. 이 정보는 worker 시점이 더 정확하므로 자동 라우팅은 worker에서 수행하는 것이 맞다.

### 3.5 모델별 제공자 차이를 감싼다

모든 후보 모델이 OpenAI 호환 `/chat/completions`를 완전히 동일하게 지원한다고 단정하면 안 된다. 당장은 OpenAI 호환 제공자를 기본으로 하되, provider adapter 계층을 두어 향후 요청/응답 포맷 차이를 흡수할 수 있게 설계한다.

### 3.6 자유 입력 대신 화이트리스트만 허용한다

사용자가 임의 문자열을 모델명으로 넣어도 그대로 upstream에 전달하면 안 된다. 운영자가 등록한 alias만 선택 가능해야 한다.

---

## 4. 목표 아키텍처

```text
Cube 요청 수신
  └─ payload 파싱
      └─ requested_model 추출 또는 없음
          └─ 큐 적재 (requested_model 포함)
              └─ worker dequeue
                  └─ 사용자 선호 모델 조회
                  └─ 큐 길이/장애 상태 조회
                  └─ resolve_model()
                      └─ provider adapter 선택
                          └─ 실제 LLM 호출
                              └─ 실패 시 fallback 체인 재시도
                                  └─ 응답 저장 및 Cube 전송
```

핵심은 `resolve_model()`이 모든 판단의 단일 진입점이 되는 구조다.

---

## 5. 구현 범위

### 5.1 모델 레지스트리 도입

[api/config.py](/Users/daeyoung/Codes/llm_chatbot/api/config.py)에 단일 `LLM_MODEL` 대신 다중 모델 레지스트리를 추가한다.

권장 설정 정보는 아래와 같다.

- alias: 외부에서 사용하는 모델 이름
- provider: `openai_compatible` 등
- model_id: upstream에 실제로 전달할 모델 ID
- base_url
- api_key
- timeout_seconds
- enabled
- routing_tier: `premium`, `balanced`, `fast` 같은 운영 분류
- fallback_models: 실패 시 재시도 후보 alias 목록

예시 개념:

```json
{
  "gpt-oss-120b": {
    "provider": "openai_compatible",
    "model_id": "gpt-oss-120b",
    "base_url": "https://...",
    "api_key": "env:LLM_API_KEY_GPT_OSS_120B",
    "timeout_seconds": 30,
    "enabled": true,
    "routing_tier": "premium",
    "fallback_models": ["gpt-oss-20b"]
  }
}
```

초기 구현에서는 `LLM_DEFAULT_MODEL`과 `LLM_MODELS_JSON` 같은 env 기반 구성이 가장 빠르다. 운영상 JSON env가 불편하면 이후 별도 설정 파일 로더로 확장한다.

### 5.2 LLM provider adapter 계층 추가

[api/llm/service.py](/Users/daeyoung/Codes/llm_chatbot/api/llm/service.py)에 모든 분기를 몰아넣지 말고 아래처럼 분리한다.

- `api/llm/models.py`: 모델 설정 dataclass
- `api/llm/registry.py`: 설정 로드 및 alias 검증
- `api/llm/router.py`: `resolve_model()` 구현
- `api/llm/providers/openai_compatible.py`: 공통 `/chat/completions` 호출

초기에는 `openai_compatible` 하나만 구현해도 충분하다. 다만 구조는 provider 추가가 가능해야 한다.

### 5.3 큐 payload에 모델 메타데이터 추가

[api/cube/models.py](/Users/daeyoung/Codes/llm_chatbot/api/cube/models.py)의 `CubeIncomingMessage`에 아래 필드를 추가한다.

- `requested_model: str | None = None`

[api/cube/payload.py](/Users/daeyoung/Codes/llm_chatbot/api/cube/payload.py)에서는 요청 본문에 `model` 필드가 있으면 이를 추출한다. 이후 UI나 외부 클라이언트가 없는 Cube 환경에서도 같은 구조를 재사용할 수 있다.

[api/cube/queue.py](/Users/daeyoung/Codes/llm_chatbot/api/cube/queue.py)는 serialize/deserialize 시 이 필드를 함께 보존해야 한다.

이 단계가 있어야 "사용자가 지정한 모델"이 비동기 worker까지 정확히 전달된다.

### 5.4 사용자 선호 모델 저장소 추가

사용자가 매번 `model`을 같이 보내지 않더라도 특정 모델을 계속 쓰고 싶을 수 있다. 이를 위해 별도 선호도 저장소를 둔다.

권장 구현:

- `api/llm/preferences.py` 또는 `api/user_preferences.py` 추가
- MongoDB가 있으면 컬렉션 저장
- MongoDB가 없으면 In-Memory 폴백

저장 키는 최소한 `user_id` 기준으로 시작한다. 향후 채널별로 분리할 필요가 있으면 `user_id + channel_id`로 확장한다.

처음부터 대화 이력 컬렉션과 섞지 않는 편이 낫다. 책임이 다르기 때문이다.

### 5.5 모델 선택 명령 처리

Cube 사용자를 위해 아래처럼 명령형 인터페이스를 추가하는 방안을 권장한다.

- `/model list`
- `/model use <alias>`
- `/model current`
- `/model reset`

이 명령은 일반 LLM 호출 전에 [api/cube/service.py](/Users/daeyoung/Codes/llm_chatbot/api/cube/service.py)에서 가로채 처리한다.

처리 원칙:

- 명령 메시지는 대화 이력에 넣지 않는다.
- 명령 응답은 즉시 텍스트로 반환한다.
- 존재하지 않는 alias는 거절한다.
- 비활성 모델은 목록에 표시하되 선택은 제한할 수 있다.

외부 API나 웹 UI가 생기면 이 명령 대신 request JSON의 `model` 필드를 그대로 활용하면 된다.

### 5.6 부하 기반 자동 라우팅 추가

자동 라우팅은 명시적 사용자 선택이 없을 때만 적용한다.

초기 정책은 단순해야 한다. 가장 현실적인 기준은 큐 길이다.

필요 추가 기능:

- [api/cube/queue.py](/Users/daeyoung/Codes/llm_chatbot/api/cube/queue.py)에 `get_queue_depth()` 추가
- ready queue 길이와 processing queue 길이를 함께 볼 수 있게 한다.

초기 라우팅 기준 예시:

- 큐가 작으면 기본 모델 사용
- 큐가 일정 임계치를 넘으면 `balanced` tier 사용
- 큐가 매우 길면 `fast` tier 사용

중요한 점은 모델명을 코드에 하드코딩하지 않는 것이다. 어떤 모델이 premium, balanced, fast인지도 설정에서 바꿀 수 있어야 한다.

### 5.7 fallback 정책 추가

모델 fallback은 아래 경우에만 적용한다.

- timeout
- network error
- upstream 5xx
- 일시적인 rate limit

아래 경우에는 fallback하지 않는다.

- 잘못된 요청 형식
- 허용되지 않은 모델명
- 잘못된 인증 설정

fallback은 "다른 모델로 한 번 더 시도" 정도의 짧은 체인으로 제한한다. 무한 재시도 구조로 만들면 안 된다.

### 5.8 로그와 관측성 추가

[api/cube/service.py](/Users/daeyoung/Codes/llm_chatbot/api/cube/service.py)와 LLM 계층 로그에는 최소한 아래 정보가 남아야 한다.

- `requested_model`
- `resolved_model`
- `fallback_from`
- `fallback_to`
- `queue_depth`
- `llm_provider`
- `llm_latency_ms`
- `llm_status`

이 정보가 있어야 운영 중 "왜 이 요청이 다른 모델로 갔는지"를 추적할 수 있다.

---

## 6. 권장 우선순위

### Phase 1. 기반 구조 추가

목표는 코드 구조를 바꾸되, 실제 동작은 기존과 동일하게 유지하는 것이다.

- 모델 레지스트리 추가
- `resolve_model()` 추가
- provider adapter 추가
- 기본 모델 1개만 등록해 기존 동작 유지

### Phase 2. 요청 모델 전달 경로 추가

- `CubeIncomingMessage`에 `requested_model` 추가
- payload 파서, queue serializer, worker 경로 업데이트
- LLM 로그에 `requested_model`, `resolved_model` 기록

### Phase 3. 사용자 선호 모델 기능 추가

- 선호 모델 저장소 구현
- `/model` 명령 처리
- 명시적 선택 시 자동 라우팅보다 우선 적용

### Phase 4. 부하 기반 자동 라우팅 추가

- 큐 길이 조회 유틸 추가
- 설정 기반 threshold 및 tier 라우팅 도입
- 운영 로그 검증

### Phase 5. fallback 및 장애 대응 추가

- 모델별 fallback chain 도입
- timeout/5xx 중심 fallback 적용
- 장애 로그와 재시도 로그 추가

이 순서가 안전한 이유는, 먼저 구조를 만들고 그 다음 정책을 올리기 때문이다.

---

## 7. 파일별 변경 계획

### 필수 수정 파일

- [api/config.py](/Users/daeyoung/Codes/llm_chatbot/api/config.py)
  다중 모델 설정 로드
- [api/llm/service.py](/Users/daeyoung/Codes/llm_chatbot/api/llm/service.py)
  단일 모델 의존 제거
- [api/cube/models.py](/Users/daeyoung/Codes/llm_chatbot/api/cube/models.py)
  `requested_model` 추가
- [api/cube/payload.py](/Users/daeyoung/Codes/llm_chatbot/api/cube/payload.py)
  요청 모델 추출
- [api/cube/queue.py](/Users/daeyoung/Codes/llm_chatbot/api/cube/queue.py)
  모델 메타데이터 직렬화 및 큐 길이 조회
- [api/cube/service.py](/Users/daeyoung/Codes/llm_chatbot/api/cube/service.py)
  명령 처리, 선호도 조회, resolver 적용, 로그 보강

### 신규 파일 권장

- `api/llm/models.py`
- `api/llm/registry.py`
- `api/llm/router.py`
- `api/llm/providers/openai_compatible.py`
- `api/llm/preferences.py`

---

## 8. 테스트 계획

아래 테스트는 반드시 추가해야 한다.

- [tests/test_llm_service.py](/Users/daeyoung/Codes/llm_chatbot/tests/test_llm_service.py)
  모델 레지스트리 로드, alias 검증, provider 호출 테스트
- [tests/test_http_clients.py](/Users/daeyoung/Codes/llm_chatbot/tests/test_http_clients.py)
  모델별 base_url/api_key/timeout 반영 테스트
- [tests/test_cube_service.py](/Users/daeyoung/Codes/llm_chatbot/tests/test_cube_service.py)
  요청 모델 전달, `/model` 명령 처리, fallback 흐름 테스트
- `tests/test_llm_router.py`
  explicit override, preference, auto routing, fallback 우선순위 테스트
- `tests/test_llm_preferences.py`
  선호 모델 저장/조회/초기화 테스트
- `tests/test_cube_queue.py`
  queue payload에 `requested_model`이 보존되는지 테스트

핵심 우선순위는 "사용자가 지정한 모델이 큐를 지나도 유지되는가"와 "자동 라우팅이 명시적 사용자 선택을 덮어쓰지 않는가"다.

---

## 9. 운영상 주의점

### 9.1 모델 특성을 코드에 박아두지 않는다

`gpt-oss-120b`가 항상 최고 품질, `gpt-oss-20b`가 항상 최저 비용이라고 코드에 하드코딩하면 운영 유연성이 떨어진다. 어떤 모델이 어떤 tier인지도 설정으로 바꾸게 해야 한다.

### 9.2 명시적 선택 우선순위를 유지한다

사용자가 특정 모델을 직접 선택했다면, 정상 가용 상태에서는 자동 분산 정책이 이를 덮어쓰지 않는 것이 맞다. 자동 라우팅은 "선택이 없을 때"의 정책이어야 한다.

### 9.3 큐 적재 시점과 worker 처리 시점을 구분한다

요청 모델은 enqueue 시점에 고정해서 보존해야 하고, 부하 판단은 worker 시점에 계산해야 한다. 이 둘을 섞으면 동작이 불안정해진다.

### 9.4 기능 플래그로 단계 배포한다

아래 플래그를 두고 단계적으로 켜는 편이 안전하다.

- `LLM_MULTI_MODEL_ENABLED`
- `LLM_USER_SELECTION_ENABLED`
- `LLM_AUTO_ROUTING_ENABLED`
- `LLM_FALLBACK_ENABLED`

---

## 10. 최종 권장안

최종적으로는 아래 순서로 구현하는 것이 가장 안전하다.

1. 단일 모델 구조를 다중 모델 레지스트리 + resolver 구조로 바꾼다.
2. 큐 payload에 `requested_model`을 포함시켜 사용자 의도를 보존한다.
3. 사용자 선호 모델 저장소와 `/model` 명령을 추가한다.
4. 명시적 선택이 없는 요청에만 큐 길이 기반 자동 라우팅을 적용한다.
5. timeout/5xx에 한해 짧은 fallback 체인을 적용한다.
6. 모든 단계에서 `requested_model`과 `resolved_model`을 로그로 남긴다.

이 계획의 핵심은 "사용자 선택", "자동 분산", "장애 fallback"을 하나의 함수에 억지로 섞지 않고, `registry -> preference -> resolver -> provider -> fallback` 순서로 책임을 분리하는 것이다.
