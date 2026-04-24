# Rich Notification - Manual Test Checklist

richnotification_rule.txt 문서를 완성하기 위해 Cube에서 직접 테스트가 필요한 항목들입니다.
테스트 결과를 기록한 뒤 규칙 문서에 반영해 주세요.

---

## 1. [x] `active` 고정값 확인

**확인 결과:** `active`의 기본값은 `true`이며 `false`는 옵션으로 사용하지 않는다.
문서에는 항상 `active: true`로 반영한다.

| 확인 항목 | 결과 |
|---|---|
| 기본값 | `true` |
| `false` 사용 가능 여부 | 사용하지 않음 |
| 문서 반영 기준 | 항상 `active: true` |

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

## 3. [x] Button `sso` 타입 및 기본 동작

**확인 결과:** `sso`는 Boolean 값인 `true` 또는 `false`를 사용한다.
기본값은 `false`이며, 내용을 읽기 위해 로그인이 필요한 경우 `true`로 설정한다.

| 확인 항목 | 결과 |
|---|---|
| 타입 | Boolean (`true` / `false`) |
| 기본값 | `false` |
| 사용 기준 | 내용을 읽기 위해 로그인해야 하는 경우 `true`로 설정 |

---

## 4. [x] Button `inner` 기본값 및 설명

**확인 결과:** Button의 `inner`는 Image/HyperText와 같은 설명을 사용한다.
기본값은 `false`다.

| 확인 항목 | 결과 |
|---|---|
| 설명 | Image/HyperText와 동일 |
| 기본값 | `false` |

---

## 5. [x] 복수 `content` 항목 동작

**확인 결과:** `content` 배열에는 여러 객체를 넣을 수 있다.
항목들은 연결된 형태로 표시되며 스크롤해서 다음 항목을 확인한다.
3개까지 테스트했고 정상 동작했다.

| 확인 항목 | 결과 |
|---|---|
| 2개의 content → 화면에 어떻게 표시? (탭 / 스크롤 / 페이지) | 연결된 형태로 표시되며 스크롤로 확인 |
| 각 content의 process가 독립적으로 동작하는지? | 연결된 UI로 이어져 보임 |
| 3개 이상도 가능한지? | 3개까지 정상 확인, 더 많은 항목도 추가 가능해 보임 |

---

## 6. [x] Callback POST payload 형식

**확인 결과:** `callbackaddress`는 POST로 수신되며 서버에서 확인한 payload 형식은 `callbaackaddress.txt` 예시와 같다.
루트 구조는 `result`, `header`, `process`를 사용한다.

| 확인 항목 | 결과 |
|---|---|
| Content-Type (form-data / json / x-www-form-urlencoded) | 서버 수신 예시는 JSON 유사 구조 payload 형태 |
| body에 포함되는 key 이름 (processid 그대로? 접두어?) | 루트에 `result`, `header`, `process` 포함 |
| radio/checkbox 복수 선택 시 value 형식 | `value`와 `text`가 배열 형태로 전달되는 예시 확인 |
| system ID (cubeuniquename 등) 실제 값 형태 | `header.from` 아래 `uniquename`, `messageid`, `client`, `companycode`, `channelid`, `username` 포함 |
| requestid에 포함 안 된 processid의 값도 전송되는지? | 추가 확인 필요 |

---

## 7. [x] `result` 필드 용도

**확인 결과:** `result` 필드는 빈 문자열 `""`로 사용한다.

| 확인 항목 | 결과 |
|---|---|
| 기본 사용값 | `""` |
| 빈 문자열 외 값 사용 여부 | 별도 사용하지 않음 |

---

## 8. [x] `session` 필드 동작

**확인 결과:** `session`은 빈 문자열 `""`을 넣어도 동작한다.

| 확인 항목 | 결과 |
|---|---|
| sessionid를 빈 문자열로 보내도 정상 동작하는지? | 정상 동작 확인 |
| 같은 sessionid로 여러 메시지 전송 시 이전 메시지가 갱신되는지? | 추가 확인 필요 |
| sequence 값에 따른 동작 차이 (순서 보장? 덮어쓰기?) | 추가 확인 필요 |

---

## 9. [x] `channelid` 전송 대상

**확인 결과:** DM 전송 시에도 `channelid`는 비워 두지 않고 `[""]`처럼 빈 문자열을 원소로 가진 배열로 채워야 한다.
`uniquename`만 유효하고 `channelid`가 `[""]`이면 사용자에게 직접 DM으로 전송된다.
`uniquename`과 실제 `channelid`를 함께 지정하면 해당 `channelid` 안의 사용자에게 전송되며, 응답은 `uniquename` 기준으로 처리된다.

| 확인 항목 | 결과 |
|---|---|
| `uniquename`만 지정할 때 `channelid` 값 | `[]`가 아니라 `[""]`로 채워야 함 |
| 채널 전체 멤버에게 전송되는지? | 아니오. `uniquename` 대상 사용자에게 전송 |
| `uniquename` + `channelid` 동시 지정 시 동작? | 지정한 채널 안의 사용자에게 전송되고, 리치노티피케이션 응답은 `uniquename` 기준으로 처리 |

---

## 10. [x] `border` Boolean 값 확인

**확인 결과:** `border`는 숫자 타입이 아니라 Boolean 값 `true` / `false`를 사용한다.
기본적으로 `false`를 쓰고, 표 형태 content를 만들 때는 `true`가 더 적합하다.

| 확인 항목 | 결과 |
|---|---|
| 허용 값 | `true` 또는 `false` |
| 기본 사용값 | 보통 `false` |
| 권장 사용 시점 | 테이블 형태 content를 만들 때 `true` 권장 |

---

## 테스트 후 할 일

1. 각 항목의 "결과" 칸을 채운다
2. 결과를 바탕으로 `richnotification_rule.txt`에 해당 섹션 업데이트
3. 이 파일에서 완료된 항목에 체크 표시
