"""Cube richnotification 메시지 모양 확인용 예제 모음.

사용법
------
1. 아래 ``CONFIG`` 블록의 자격증명, ``USER_ID``, ``CHANNEL_ID``를 본인 값으로 채운다.
2. ``main()`` 안에서 보고 싶은 예제 함수만 주석을 풀어 호출한다.
3. 프로젝트 루트에서 다음과 같이 실행 (또는 IDE의 Run 버튼)::

       python -m devtools.cube_message.examples

⚠ 주의
------
``API_ID`` / ``API_TOKEN``을 그대로 채운 상태로 커밋하지 말 것.
공유 전에는 빈 문자열로 되돌리거나 ``git restore`` / ``git update-index --skip-worktree``
등으로 로컬 편집만 유지한다.

``.env``를 쓰는 팀원이라면 ``CONFIG = CubeMessageConfig.from_env()``로 바꾸면 된다.

자세한 블록 종류는 ``devtools/cube_message/blocks.py`` 참조.
"""

import logging

from devtools.cube_message import blocks, samples
from devtools.cube_message.client import CubeMessageConfig, send_blocks, send_text

# ---------------------------------------------------------------------------
# 본인 정보로 직접 채운다. 커밋 전에 빈 문자열로 되돌릴 것.
CONFIG = CubeMessageConfig.inline(
    api_id="",
    api_token="",
    bot_username="ITC OSS",
)
USER_ID = "your.cube.id"
CHANNEL_ID = "your.channel.id"
# ---------------------------------------------------------------------------


def example_text() -> None:
    """가장 단순한 한 줄 텍스트."""

    send_text(
        "안녕하세요, Cube 메시지 테스트입니다.",
        user_id=USER_ID,
        channel_id=CHANNEL_ID,
        config=CONFIG,
    )


def example_styled_text() -> None:
    """색상과 정렬을 바꿔 여러 줄 출력."""

    send_blocks(
        blocks.add_text("📌 작업 결과 요약", color="#0066cc", align="center"),
        blocks.add_text("- 처리 건수: 128"),
        blocks.add_text("- 실패 건수: 0", color="#22aa22"),
        blocks.add_text("- 소요 시간: 1.4초"),
        user_id=USER_ID,
        channel_id=CHANNEL_ID,
        config=CONFIG,
    )


def example_table() -> None:
    """헤더 + 본문 행으로 구성된 그리드 표."""

    send_blocks(
        blocks.add_text("주간 작업 통계", align="center"),
        blocks.add_table(
            headers=["요일", "처리 건", "실패 건"],
            rows=[
                ["월", "120", "0"],
                ["화", "98", "1"],
                ["수", "144", "0"],
            ],
        ),
        user_id=USER_ID,
        channel_id=CHANNEL_ID,
        config=CONFIG,
    )


def example_hyperlink() -> None:
    """표 본문에 하이퍼링크 셀을 넣는다."""

    send_blocks(
        blocks.add_text("바로가기 링크 모음"),
        blocks.add_table(
            headers=["문서", "링크"],
            rows=[
                ["사내 위키", blocks.make_hypertext_cell("열기", "https://wiki.skhynix.com")],
                ["대시보드", blocks.make_hypertext_cell("열기", "https://dashboard.skhynix.com")],
            ],
        ),
        user_id=USER_ID,
        channel_id=CHANNEL_ID,
        config=CONFIG,
    )


def example_select_callback() -> None:
    """select 셀. 사용자가 선택하면 콜백 URL로 결과가 전달된다.

    ``add_select`` 같이 ``requestid``를 가진 블록이 하나라도 있으면
    ``send_blocks``가 자동으로 콜백 주소를 채워 넣는다.
    """

    send_blocks(
        blocks.add_text("처리 모드를 선택해 주세요."),
        blocks.add_select(
            label="모드",
            options=[("자동", "auto"), ("수동", "manual")],
            processid="SelectMode",
            required=True,
            alertmsg="모드를 선택해야 진행할 수 있습니다.",
        ),
        user_id=USER_ID,
        channel_id=CHANNEL_ID,
        config=CONFIG,
    )


def example_verified_sample(number: int = 1) -> None:
    """``richnotification_samples.md``에 있는 검증된 샘플을 그대로 전송.

    사용 가능한 번호는 ``samples.list_samples()``로 확인할 수 있다.
    ``send_sample``은 헤더(from/token/to)만 ``CONFIG`` 값으로 채우고 본문은
    문서의 JSON을 손대지 않는다.
    """

    available = samples.list_samples()
    print("사용 가능한 샘플:")
    for num, title in available.items():
        print(f"  {num}: {title}")

    samples.send_sample(number, user_id=USER_ID, channel_id=CHANNEL_ID, config=CONFIG)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if not CONFIG.bot_id or not CONFIG.bot_token:
        raise SystemExit("CONFIG의 api_id/api_token을 채워야 실행할 수 있습니다 (examples.py 상단 참조).")
    if USER_ID.startswith("your.") or CHANNEL_ID.startswith("your."):
        raise SystemExit("USER_ID / CHANNEL_ID를 본인 Cube 정보로 바꾸어야 합니다.")

    # 보내고 싶은 예제만 주석을 풀어서 실행한다.
    example_text()
    # example_styled_text()
    # example_table()
    # example_hyperlink()
    # example_select_callback()
    # example_verified_sample(1)


if __name__ == "__main__":
    main()
