"""Cube richnotification 규칙/한계 탐색용 standalone 샘플.

각 함수는 ``Block`` 리스트를 반환한다. ``send_blocks(*sample(), ...)`` 또는
``send_sample(name, ...)``로 Cube에 전송해 실제 렌더링을 확인하고,
그 결과를 ``richnotification_rule.txt``에 반영하기 위한 작은 실험 모음이다.

각 샘플은 한두 개의 변수만 노출하도록 최소화되어 있으며, 무엇을 확인하려는지
docstring에 ``확인 포인트:``로 적었다.

사용 예::

    from devtools.cube_message import samples
    samples.send_sample("label_basics", user_id=..., channel_id=..., config=CONFIG)

새 샘플을 추가할 때는 (1) 함수 작성 (2) ``SAMPLES``에 한 줄 설명 추가
(3) ``_FACTORIES``에 매핑 등록 — 세 곳을 함께 수정한다.
"""

from collections.abc import Callable
from typing import Any

from devtools.cube_message import blocks
from devtools.cube_message.client import CubeMessageConfig, send_blocks


def text_baseline() -> list[blocks.Block]:
    """단순 한 줄 텍스트 — 연결/자격증명 sanity check.

    확인 포인트:
    - 메시지가 본인 DM/채널에 도달하는가
    - 한국어 텍스트가 깨지지 않는가
    """

    return [blocks.add_text("Cube 메시지 테스트 (baseline)")]


def label_basics() -> list[blocks.Block]:
    """라벨 색상/정렬/bgcolor 렌더링 확인.

    확인 포인트:
    - hex 색상(``#RRGGBB``)이 의도대로 적용되는가
    - ``align="center"`` / ``"right"``가 텍스트 자체에도 반영되는가
    - 셀 ``bgcolor``가 채워졌을 때 라벨 영역이 정말로 색칠되는가
    - 5요소 언어 배열에서 한국어(0번)만 채워도 문제없는가
    """

    return [
        blocks.add_text("기본 검정 라벨 (#000000, left)"),
        blocks.add_text("진한 파랑 라벨 (#0066cc, center)", color="#0066cc", align="center"),
        blocks.add_text("진한 빨강 라벨 (#cc2222, right)", color="#cc2222", align="right"),
        blocks.add_row(
            [blocks.make_label_cell("배경색이 있는 라벨", bgcolor="#fff5cc", color="#664400")],
        ),
    ]


def column_widths() -> list[blocks.Block]:
    """컬럼 너비 비율(%, px, auto) 분배 확인.

    확인 포인트:
    - ``%`` 단위가 모바일/데스크톱에서 동일하게 분배되는가
    - ``"100px"`` 같은 픽셀 단위가 인정되는가
    - ``""`` (auto)와 ``"%"``가 한 행에 섞이면 어떻게 되는가
    - 행 내부 width 합계가 100%를 넘기면 어떻게 잘리는가
    """

    return [
        blocks.add_text("== 단일 100% ==", color="#666666"),
        blocks.add_row([blocks.make_label_cell("100% 라벨", border=True)]),
        blocks.add_text("== 50% / 50% ==", color="#666666"),
        blocks.add_row(
            [
                blocks.make_label_cell("왼쪽 50%", width="50%", border=True),
                blocks.make_label_cell("오른쪽 50%", width="50%", border=True),
            ]
        ),
        blocks.add_text("== 25% / 75% ==", color="#666666"),
        blocks.add_row(
            [
                blocks.make_label_cell("25%", width="25%", border=True),
                blocks.make_label_cell("75%", width="75%", border=True),
            ]
        ),
        blocks.add_text("== 100px / auto ==", color="#666666"),
        blocks.add_row(
            [
                blocks.make_label_cell("100px", width="100px", border=True),
                blocks.make_label_cell('auto("")', width="", border=True),
            ]
        ),
    ]


def grid_table() -> list[blocks.Block]:
    """``bodystyle="grid"`` 표 렌더링 확인.

    확인 포인트:
    - 헤더 행과 본문 행의 ``bgcolor`` 대비가 표처럼 보이는가
    - ``border=True``가 셀별로 그려지는지, 행 단위인지
    - 빈 문자열 셀이 그리드 구조를 깨뜨리지 않는가
    """

    return [
        blocks.add_table(
            headers=["요일", "처리 건", "실패 건", "비고"],
            rows=[
                ["월", "120", "0", ""],
                ["화", "98", "1", "재시도 1건"],
                ["수", "144", "0", ""],
                ["목", "", "", "휴무"],
            ],
        ),
    ]


def approval_buttons() -> list[blocks.Block]:
    """승인/반려 버튼 + ``confirmmsg`` + 콜백 동작 확인.

    확인 포인트:
    - 버튼 ``bgcolor`` / ``textcolor``가 그대로 표시되는가
    - ``confirmmsg``가 클릭 시 다이얼로그로 뜨는가
    - 콜백 payload에 ``processid`` / ``value``가 정상 포함되는가
    - 두 버튼이 한 행 50%/50%로 나란히 배치되는가
    """

    return [
        blocks.add_text("📌 휴가 신청 결재 (테스트)", color="#0066cc", align="center"),
        blocks.add_text("신청자: 홍길동", color="#666666"),
        blocks.add_text("기간: 2026-05-10 ~ 2026-05-12", color="#666666"),
        blocks.add_row(
            [
                _button_cell(
                    "승인",
                    processid="AgreeButton",
                    value="approve",
                    bgcolor="#22aa22",
                    textcolor="#ffffff",
                    confirmmsg="승인하시겠습니까?",
                    width="50%",
                ),
                _button_cell(
                    "반려",
                    processid="RejectButton",
                    value="reject",
                    bgcolor="#cc4444",
                    textcolor="#ffffff",
                    confirmmsg="반려하시겠습니까?",
                    width="50%",
                ),
            ],
            align="center",
            requestid=["AgreeButton", "RejectButton"],
        ),
    ]


def hyperlink_card() -> list[blocks.Block]:
    """하이퍼링크 + opengraph 미리보기 동작 확인.

    확인 포인트:
    - ``opengraph=True``일 때 미리보기 카드가 자동 생성되는가
    - ``inner=True`` / ``False``가 인앱 vs 외부 브라우저를 결정하는가
    - 두 하이퍼링크를 연속으로 두면 카드가 각각 그려지는가
    """

    return [
        blocks.add_text("문서 바로가기"),
        blocks.add_row(
            [
                blocks.make_hypertext_cell(
                    "사내 위키 — 운영 가이드",
                    "https://wiki.skhynix.com",
                    opengraph=True,
                    inner=True,
                )
            ]
        ),
        blocks.add_row(
            [
                blocks.make_hypertext_cell(
                    "외부 링크 (opengraph 끔)",
                    "https://www.skhynix.com",
                    opengraph=False,
                    inner=False,
                )
            ]
        ),
    ]


def _button_cell(
    text: str,
    *,
    processid: str,
    value: str,
    bgcolor: str = "",
    textcolor: str = "",
    confirmmsg: str = "",
    width: str = "100%",
    clickurl: str = "",
) -> dict[str, Any]:
    """버튼 셀 — blocks.py에 헬퍼가 없어 raw dict로 직접 구성."""

    return {
        "bgcolor": "",
        "border": False,
        "align": "center",
        "valign": "middle",
        "width": width,
        "type": "button",
        "control": {
            "processid": processid,
            "active": True,
            "text": [text, "", "", "", ""],
            "confirmmsg": confirmmsg,
            "value": value,
            "bgcolor": bgcolor,
            "textcolor": textcolor,
            "align": "center",
            "clickurl": clickurl,
            "androidurl": "",
            "iosurl": "",
            "popupoption": "",
            "sso": False,
            "inner": False,
        },
    }


SAMPLES: dict[str, str] = {
    "text_baseline": "단순 한 줄 텍스트 (sanity check)",
    "label_basics": "라벨 색상/정렬/bgcolor 렌더링",
    "column_widths": "컬럼 너비(%, px, auto) 분배",
    "grid_table": "bodystyle=grid 표 렌더링",
    "approval_buttons": "버튼 + confirmmsg + 콜백",
    "hyperlink_card": "하이퍼링크 + opengraph",
}

_FACTORIES: dict[str, Callable[[], list[blocks.Block]]] = {
    "text_baseline": text_baseline,
    "label_basics": label_basics,
    "column_widths": column_widths,
    "grid_table": grid_table,
    "approval_buttons": approval_buttons,
    "hyperlink_card": hyperlink_card,
}


def list_samples() -> dict[str, str]:
    """샘플 이름 → 한 줄 설명 매핑."""

    return dict(SAMPLES)


def send_sample(
    name: str,
    *,
    user_id: str,
    channel_id: str,
    config: CubeMessageConfig | None = None,
) -> dict[str, Any] | None:
    """이름으로 샘플을 골라 Cube에 전송."""

    factory = _FACTORIES.get(name)
    if factory is None:
        raise ValueError(f"알 수 없는 샘플: {name!r}. 사용 가능: {sorted(_FACTORIES)}")
    return send_blocks(*factory(), user_id=user_id, channel_id=channel_id, config=config)
