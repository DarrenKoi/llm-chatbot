# Rich Notification - Manual Test Checklist

richnotification_rule.txt 문서를 완성하기 위해 Cube에서 직접 테스트가 필요한 항목들입니다.
테스트 결과를 기록한 뒤 규칙 문서에 반영해 주세요.

---

## 1. `active: false` 동작 확인

**현재 상태:** 문서에 `active`는 보통 `true`라고만 기술됨. `false`일 때 동작이 정의되지 않음.

**테스트 방법:** 아래 control type별로 `active: false`를 설정하여 전송

| Control Type | 테스트 | 결과 (숨김 / 비활성화 / 회색처리 / 기타) |
|---|---|---|
| label | `"active": false` | |
| button | `"active": false` | |
| inputtext | `"active": false` | |
| radio | `"active": false` | |
| checkbox | `"active": false` | |
| select | `"active": false` | |

---

## 2. [x] Button `popupoption` 기본값 및 용도

**확인 결과:** `popupoption`은 Button에서 `linkurl` 또는 `clickurl`과 함께 사용한다.
기본값은 `""`(빈 문자열)이며, 목적은 `linkurl` 또는 `clickurl`로 가져온 내용을 브라우저에 표시하는 것이다.

| 확인 항목 | 결과 |
|---|---|
| 사용 URL 필드 | `linkurl` 또는 `clickurl` |
| 기본값 | `""` (빈 문자열) |
| 용도 | `linkurl` 또는 `clickurl`의 내용을 브라우저에 표시 |

---

## 3. Button `sso` 타입 및 동작

**현재 상태:** `sso`가 Boolean이라고 되어있지만 "normally empty"라고도 되어 있어 타입이 불확실.

**테스트 방법:**

| sso 값 | clickurl 설정 | 결과 (SSO 토큰 포함 여부 / 동작) |
|---|---|---|
| `""` (빈 문자열) | 있음 | |
| `true` | 있음 | |
| `false` | 있음 | |

---

## 4. Button `inner` 동작

**현재 상태:** Image/HyperText에서는 "DMZ 내부 URL 여부"로 설명되지만, Button에서는 설명 없음.

**테스트 방법:**

| inner 값 | clickurl | 결과 (내부 브라우저 / 외부 브라우저 / 기타) |
|---|---|---|
| `true` | 내부 URL | |
| `false` | 외부 URL | |
| `true` | 외부 URL | |

---

## 5. 복수 content 항목 동작

**현재 상태:** `content`가 배열이지만 복수 항목의 용도가 문서화되지 않음.

**테스트 방법:**
```json
"content": [
    { "header": {}, "body": {...첫 번째...}, "process": {...} },
    { "header": {}, "body": {...두 번째...}, "process": {...} }
]
```

| 테스트 항목 | 결과 |
|---|---|
| 2개의 content → 화면에 어떻게 표시? (탭 / 스크롤 / 페이지) | |
| 각 content의 process가 독립적으로 동작하는지? | |
| 3개 이상도 가능한지? | |

---

## 6. Callback POST 응답 형식

**현재 상태:** `callbackaddress`로 POST가 전송된다고만 기술됨. 실제 body 형식이 문서화되지 않음.

**테스트 방법:** 간단한 form (inputtext + button)을 만들고 callback 서버에서 request body를 로깅

| 확인 항목 | 결과 |
|---|---|
| Content-Type (form-data / json / x-www-form-urlencoded) | |
| body에 포함되는 key 이름 (processid 그대로? 접두어?) | |
| radio/checkbox 복수 선택 시 value 형식 | |
| system ID (cubeuniquename 등) 실제 값 형태 | |
| requestid에 포함 안 된 processid의 값도 전송되는지? | |

---

## 7. `result` 필드 용도

**현재 상태:** "typically empty"로만 기술됨.

| 확인 항목 | 결과 |
|---|---|
| 빈 문자열 외에 값을 넣으면 어떻게 되는지? | |
| Cube가 응답 시 result에 값을 채워주는지? | |

---

## 8. `session` 필드 동작

**현재 상태:** sessionid/sequence 예시만 있고 동작 설명이 없음.

| 확인 항목 | 결과 |
|---|---|
| 같은 sessionid로 여러 메시지 전송 시 이전 메시지가 갱신되는지? | |
| sequence 값에 따른 동작 차이 (순서 보장? 덮어쓰기?) | |
| sessionid를 빈 문자열로 보내도 정상 동작하는지? | |

---

## 9. `channelid` 전송 대상

**현재 상태:** channelid가 채널 ID 배열이라고만 기술됨.

| 확인 항목 | 결과 |
|---|---|
| 채널 전체 멤버에게 전송되는지? | |
| 채널 내 메시지로 게시되는지? | |
| uniquename + channelid 동시 지정 시 동작? | |

---

## 10. Numeric Values 설명 정정 확인

**현재 상태:** "Data Type Rules > Numeric Values" 섹션에 `"In numbers: true, false (for border)"`라고 되어 있음. Boolean과 혼동됨.

| 확인 항목 | 결과 |
|---|---|
| `border: 1` / `border: 0` 으로 보내도 동작하는지? | |
| `border: "true"` (문자열)로 보내도 동작하는지? | |

---

## 테스트 후 할 일

1. 각 항목의 "결과" 칸을 채운다
2. 결과를 바탕으로 `richnotification_rule.txt`에 해당 섹션 업데이트
3. 이 파일에서 완료된 항목에 체크 표시
