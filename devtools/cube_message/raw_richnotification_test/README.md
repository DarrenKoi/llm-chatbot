# raw_richnotification_test

Cube `richnotification` payload JSON 파일을 **그대로** Cube에 POST해서 실제 화면 렌더링을 확인하는 개발용 도구다. 블록 빌더(`devtools/cube_message/blocks.py`)를 거치지 않고 JSON을 직접 보낼 수 있어, 새 페이로드 규칙을 검증하거나 다른 시스템에서 만든 페이로드를 그대로 재현할 때 쓴다.

## 디렉터리 구성

| 경로 | 설명 |
|------|------|
| `raw_rich_test.py` | 실행 스크립트. 어떤 샘플을 보낼지 `main()`에서 주석으로 선택한다. |
| `config.py` | 자격증명·전송 대상 ID·기본 콜백 주소 등의 로컬 설정. |
| `samples/` | 모든 raw richnotification JSON 샘플이 모이는 곳. 새 페이로드를 추가하려면 이 폴더에 파일을 떨어뜨리면 된다. |
| `samples/text_summary.json` | 텍스트 요약 카드 샘플. |
| `samples/grid_table.json` | 그리드 테이블 샘플. |
| `samples/select_callback.json` | select 콜백 샘플. `callbackaddress`가 비어 있으면 config 값으로 채워진다. |
| `samples/extensionless_sample` | 확장자가 없어도 로드되는지 확인하는 샘플. |

## 빠른 사용법

1. **`config.py`를 채운다.** 봇 ID/토큰과 본인 Cube `uniquename`이 필요하다. 비어 있는 값은 프로젝트 루트의 `.env`에서 자동 보충된다 (`CubeMessageConfig.from_env()`). richnotification URL은 `client.py`의 `DEFAULT_CUBE_API_URL`에서 자동으로 가져오므로 따로 설정하지 않는다.

   ```python
   # config.py
   HEADER_FROM = ""                    # 봇 ID
   HEADER_TOKEN = ""                   # 봇 토큰
   HEADER_FROMUSERNAME = "ITC OSS"     # 단일 문자열은 5개 슬롯 모두 같은 값으로 채워짐
   HEADER_TO_UNIQUENAME = "your.cube.id"  # 반드시 본인 Cube ID로 변경
   HEADER_TO_CHANNELID = ""            # DM이면 빈 문자열
   PROCESS_CALLBACKADDRESS = ""        # select 등 콜백을 쓸 때만 채우면 된다
   ```

   ⚠ 토큰이 들어 있는 상태로 커밋하지 말 것. 공유 전에 빈 문자열로 되돌리거나 `git update-index --skip-worktree`로 로컬 편집만 유지한다.

2. **보낼 샘플을 고른다.** `raw_rich_test.py` 하단의 `main()`에서 보내고 싶은 함수만 주석을 푼다.

   ```python
   def main() -> None:
       ...
       sample_text_summary()
       # sample_grid_table()
       # sample_select_callback()
       # sample_extensionless()
       # sample_all()  # samples/ 안의 모든 파일을 2초 간격으로 순회 전송
   ```

3. **실행한다.** IDE의 Run 버튼을 누르거나, 어떤 작업 디렉터리에서든 다음과 같이 실행한다.

   ```bash
   python devtools/cube_message/raw_richnotification_test/raw_rich_test.py
   ```

   스크립트 상단의 `sys.path` 부트스트랩이 프로젝트 루트를 자동으로 추가하므로 `python -m`이나 `cd`가 필요 없다.

## 헤더/콜백 자동 채우기

`send_raw_file()` 호출은 기본값으로 다음을 수행한다.

- `richnotification.header.from` / `token` / `fromusername` / `to.uniquename` / `to.channelid`를 `config.py` 값으로 덮어쓴다 (`FILL_HEADER = True`).
- 각 `content[].process`에서 `callbacktype`이 비어 있으면 `"url"`을 넣고, `callbacktype == "url"`이면서 `callbackaddress`가 비어 있는 항목에 `config.callback_url`을 채운다 (`FILL_CALLBACK = True`).

JSON 파일에 적힌 헤더/콜백을 그대로 보내고 싶다면 `fill_header=False`, `fill_callback=False`를 인자로 넘긴다.

```python
send_raw_file("text_summary.json", fill_header=False, fill_callback=False)
```

## 직접 만든 JSON 보내기

`samples/` 디렉터리에 자신의 `richnotification` JSON 파일을 추가한 뒤 새 함수에서 `send_raw_file()`을 호출한다.

```python
def sample_my_payload() -> None:
    send_raw_file("my_payload.json")
```

`{"richnotification": { ... }}` 형태의 최상위 키를 반드시 포함해야 한다. 확장자가 없어도 로드된다 (`extensionless_sample` 참고).

## 일괄 검증 (iteration mode)

`samples/` 폴더에 쌓인 모든 페이로드를 한 번에 검증하려면 `sample_all()` (또는 `send_all_samples()`)을 사용한다. Cube의 대역폭/연속 전송 제한을 피하기 위해 매 요청 사이에 `ITERATION_DELAY_SECONDS`(기본 **2초**) 만큼 대기한다.

```python
from devtools.cube_message.raw_richnotification_test import send_all_samples

# 기본 2초 간격
send_all_samples()

# 더 느리게 보내고 싶으면 직접 지정
send_all_samples(delay_seconds=5.0)
```

순회는 파일명의 알파벳 순서로 진행되며, 각 단계마다 `[1/4] grid_table.json` 형태의 진행 표시를 출력한다.

## 주요 함수

| 함수 | 용도 |
|------|------|
| `send_raw_file(path_or_name, ...)` | JSON 파일을 로드해 헤더/콜백을 보정하고 POST한다. 결과를 표준 출력으로 보여 준다. |
| `send_all_samples(delay_seconds=2.0, ...)` | `samples/` 디렉터리의 모든 파일을 지정한 간격으로 순차 전송. |
| `load_raw_richnotification(path_or_name)` | JSON을 읽어 dict로 반환 (보정 없음). 페이로드를 직접 다루고 싶을 때 사용. |
| `apply_raw_test_config(payload, ...)` | 메모리 상의 페이로드 사본에만 헤더/콜백을 채운다. |
| `build_cube_message_config()` | `config.py`를 우선 적용하고 빈 값은 `.env`로 보충한 `CubeMessageConfig`를 반환. |
| `list_richnotification_files()` | `samples/` 디렉터리에서 사용 가능한 샘플 파일 경로 목록. |

## 트러블슈팅

- **`config.py의 HEADER_TO_UNIQUENAME을 본인 Cube ID로 바꿔야 실행할 수 있습니다.`** → `HEADER_TO_UNIQUENAME`이 `your.cube.id` 그대로다. 본인 Cube ID로 교체.
- **`raw richnotification 파일은 'richnotification' 객체를 포함해야 합니다.`** → 최상위가 `{"richnotification": {...}}` 인지 확인.
- **`Cube richnotification HTTP 4xx`** → 봇 ID/토큰, `to.uniquename` 값을 확인. 사내망에서만 도달 가능한 URL이라면 사무실 환경에서 실행해야 한다.
