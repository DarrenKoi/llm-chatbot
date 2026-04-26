# Cube Message Devtools

Cube에서 메시지가 어떻게 보이는지 빠르게 확인하기 위한 standalone 헬퍼.
Flask 앱(`api.config`)을 임포트하지 않고, 자격증명을 코드에 직접 적거나
`.env`에서 읽어 `httpx`로 곧장 요청을 보낸다. richnotification 엔드포인트만
지원한다 (multiMessage는 평문 한정이라 devtools에서는 제거).

## 파일 구성

| 파일          | 역할                                                              |
| ------------- | ----------------------------------------------------------------- |
| `blocks.py`   | text/table/hyperlink/select 등 블록 빌더                          |
| `client.py`   | `.env` 로드 + `send_text` / `send_blocks` (실제 전송)             |
| `examples.py` | 본인 ID를 채워 넣고 실행하는 샘플 모음 — **여기를 편집해 사용**   |

## 사용법 (권장: 코드에 직접 자격증명 적기)

`examples.py`를 열고 상단의 `CONFIG`, `USER_ID`, `CHANNEL_ID`를 본인 정보로
채운 뒤, `main()`에서 보내고 싶은 예제 함수만 주석을 풀고 실행한다.

```bash
python -m devtools.cube_message.examples
```

IDE의 Run 버튼으로 직접 실행해도 된다. CLI 인자는 없으며, 모든 값은 파일 안에
직접 적는다.

> ⚠ `examples.py`에 자격증명을 채운 상태로 커밋하지 말 것.
> 커밋 전 빈 문자열로 되돌리거나 `git update-index --skip-worktree examples.py`로
> 로컬 편집만 유지한다.

## 임포트해서 쓰기

```python
from devtools.cube_message import blocks, send_blocks, send_text
from devtools.cube_message.client import CubeMessageConfig

# (A) 자격증명을 코드에 직접 적기
CONFIG = CubeMessageConfig.inline(api_id="...", api_token="...")

# (B) .env에서 읽어오기
# CONFIG = CubeMessageConfig.from_env()

send_text("안녕하세요", user_id="cube.user", channel_id="cube.channel", config=CONFIG)

send_blocks(
    blocks.add_text("📌 작업 결과", color="#0066cc"),
    blocks.add_table(
        headers=["요일", "건수"],
        rows=[["월", "120"], ["화", "98"]],
    ),
    user_id="cube.user",
    channel_id="cube.channel",
    config=CONFIG,
)
```

`add_select`처럼 `requestid`가 있는 블록을 포함하면 `send_blocks`가 자동으로
콜백 주소(`callback_url`)를 채워 넣는다. `config`를 생략하면 `from_env()`가 호출된다.

## (선택) `.env` 환경변수

`from_env()`를 쓸 때 참조하는 키.

| 키                                  | 설명                                               |
| ----------------------------------- | -------------------------------------------------- |
| `CUBE_API_ID` / `CUBE_API_TOKEN`    | 봇 인증 (필수)                                     |
| `CUBE_BOT_ID` / `CUBE_BOT_TOKEN`    | 별도 봇 사용 시. 비우면 `CUBE_API_*`로 대체        |
| `CUBE_BOT_USERNAMES`                | 봇 표시 이름. 콤마로 다국어 분리 (선택)            |
| `CUBE_RICHNOTIFICATION_URL`         | 엔드포인트 오버라이드 (선택)                       |
| `CUBE_RICHNOTIFICATION_CALLBACK_URL`| select 등 콜백 주소 (선택)                         |
| `CUBE_TIMEOUT_SECONDS`              | HTTP 타임아웃, 기본 10초 (선택)                    |
