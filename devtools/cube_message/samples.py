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

from api.cube import rich_blocks as prod_blocks
from devtools.cube_message import blocks
from devtools.cube_message.client import CubeMessageConfig, send_blocks

# api.cube.rich_blocks는 api.config / Flask에 의존하지 않는 순수 스키마 모듈이라
# devtools에서 직접 임포트해도 standalone 원칙을 깨지 않는다. 프로덕션의 모든
# add_* 헬퍼(button/choice/input/datepicker/image 등)를 그대로 시연하기 위함.


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


# ---------------------------------------------------------------------------
# 아래는 프로덕션(api.cube.rich_blocks) 헬퍼를 그대로 호출하는 probe들이다.
# Block dataclass의 필드 구조가 devtools/blocks.py와 동일해서 send_blocks가
# duck-typing으로 그대로 처리한다.
# ---------------------------------------------------------------------------


def buttons_basic() -> list[Any]:
    """프로덕션 ``add_button`` 동작 확인.

    확인 포인트:
    - ``bgcolor`` / ``textcolor``가 그대로 적용되는가
    - ``confirmmsg``가 클릭 시 다이얼로그로 뜨는가
    - ``clickurl``이 채워졌을 때 콜백 대신 URL로 이동하는가
    """

    return [
        prod_blocks.add_text("버튼 셀 렌더링 (production add_button)"),
        prod_blocks.add_button("기본 버튼", processid="SendButton", value="default"),
        prod_blocks.add_button(
            "초록 + 확인 다이얼로그",
            processid="ConfirmButton",
            value="confirm",
            bgcolor="#22aa22",
            textcolor="#ffffff",
            confirmmsg="진행하시겠습니까?",
        ),
        prod_blocks.add_button(
            "URL로 이동 (clickurl)",
            processid="OpenButton",
            value="open",
            clickurl="https://www.skhynix.com",
        ),
    ]


def radio_choice() -> list[Any]:
    """단일 선택 라디오 그룹 (``add_choice(multi=False)``).

    확인 포인트:
    - 옵션이 라디오 버튼으로 그려지는가 (드롭다운이 아닌)
    - ``default_value``가 첫 진입 시 선택되어 있는가
    - 필수 선택을 비우면 ``alertmsg``가 뜨는가
    """

    return [
        prod_blocks.add_text("어떤 형식으로 받으시겠어요?"),
        prod_blocks.add_choice(
            "출력 형식",
            [("PDF", "pdf"), ("엑셀", "xlsx"), ("CSV", "csv")],
            processid="SelectFormat",
            multi=False,
            default_value="pdf",
            required=True,
            alertmsg="형식을 선택해 주세요.",
        ),
    ]


def checkbox_choice() -> list[Any]:
    """다중 선택 체크박스 그룹 (``add_choice(multi=True)``).

    확인 포인트:
    - 다중 선택이 가능한가
    - 콜백 payload에 ``value`` 배열로 들어오는가
    """

    return [
        prod_blocks.add_text("받고 싶은 알림 종류를 모두 선택하세요."),
        prod_blocks.add_choice(
            "알림 채널",
            [("이메일", "email"), ("SMS", "sms"), ("Cube DM", "cube"), ("Teams", "teams")],
            processid="SelectChannels",
            multi=True,
            required=True,
            alertmsg="최소 하나 이상 선택해 주세요.",
        ),
    ]


def select_dropdown() -> list[Any]:
    """드롭다운 선택 (``add_select``) — 라디오와 렌더링 차이 비교.

    확인 포인트:
    - 라디오 그룹과 시각적으로 어떻게 다른가
    - 옵션이 많을 때 스크롤되는 형태가 어떤가
    - ``default_value``가 미리 선택되어 보이는가
    """

    return [
        prod_blocks.add_text("부서를 선택하세요."),
        prod_blocks.add_select(
            "부서",
            [
                ("ITC", "itc"),
                ("Foundry", "foundry"),
                ("Memory", "memory"),
                ("Logic", "logic"),
                ("HR", "hr"),
            ],
            processid="SelectDepartment",
            default_value="itc",
            required=True,
            alertmsg="부서를 선택해 주세요.",
        ),
    ]


def input_field() -> list[Any]:
    """단일 행 입력 (``add_input``).

    확인 포인트:
    - ``placeholder``가 회색 힌트로 보이는가
    - ``min_length`` / ``max_length`` 위반 시 ``validmsg``가 언제 트리거되는가
    - ``default``가 있을 때 입력칸이 채워진 상태로 시작하는가
    """

    return [
        prod_blocks.add_text("사번을 입력해 주세요."),
        prod_blocks.add_input(
            "사번",
            processid="InputEmployeeId",
            placeholder="X905552",
            min_length=7,
            max_length=7,
            validmsg="사번은 7자리입니다.",
            required=True,
            alertmsg="사번을 입력해 주세요.",
        ),
    ]


def textarea_field() -> list[Any]:
    """다중 행 입력 (``add_textarea``).

    확인 포인트:
    - ``height`` 파라미터가 입력 영역 높이에 반영되는가
    - 줄 바꿈이 입력 안에서 자연스러운가
    - 길이 제한 위반 시 ``validmsg``가 작동하는가
    """

    return [
        prod_blocks.add_text("의견을 자유롭게 적어주세요."),
        prod_blocks.add_textarea(
            "의견",
            processid="Comment",
            placeholder="개선 제안, 불편 사항 등...",
            height="120px",
            min_length=10,
            max_length=500,
            validmsg="10자 이상 500자 이하로 작성해 주세요.",
            required=False,
        ),
    ]


def datepicker_basic() -> list[Any]:
    """날짜 선택 (``add_datepicker``).

    확인 포인트:
    - ``default``(YYYY/MM/DD)가 picker에 미리 설정되는가
    - 한국어 환경에서 캘린더 UI가 정상 표시되는가
    - 날짜 포맷이 callback payload에 그대로 돌아오는가
    """

    return [
        prod_blocks.add_text("출장 시작일을 선택하세요."),
        prod_blocks.add_datepicker(
            "출장일",
            processid="SelectDate",
            default="2026/05/01",
            required=True,
            alertmsg="출장일을 선택해 주세요.",
        ),
    ]


def datetimepicker_basic() -> list[Any]:
    """날짜+시간 선택 (``add_datetimepicker``).

    확인 포인트:
    - ``default``(YYYY/MM/DD HH:MM)가 picker에 반영되는가
    - 분 단위 선택 UI는 어떻게 그려지는가
    - timezone 표시가 있는가
    """

    return [
        prod_blocks.add_text("회의 시작 시각을 선택하세요."),
        prod_blocks.add_datetimepicker(
            "회의 시작",
            processid="SelectDateTime",
            default="2026/05/01 14:00",
            required=True,
            alertmsg="시각을 선택해 주세요.",
        ),
    ]


def image_basic() -> list[Any]:
    """이미지 카드 (``add_image``).

    확인 포인트:
    - ``displaytype="resize"``가 width 100% 기준으로 자동 조정되는가
    - ``location=True`` (DMZ 내부) 가정이 실제와 맞는가
    - ``linkurl`` 클릭 시 inner=True 동작 (인앱 vs 외부)

    Note: ``source_url``은 본인 환경에 맞는 이미지 경로로 바꿔서 확인할 것.
    """

    return [
        prod_blocks.add_text("이미지 렌더링 테스트"),
        prod_blocks.add_image(
            source_url="10.158.122.138/Resource/Image/test.png",
            alt="테스트 이미지",
            linkurl="https://www.skhynix.com",
            displaytype="resize",
            width="100%",
            location=True,
            inner=True,
        ),
    ]


def mixed_form() -> list[Any]:
    """텍스트 + 선택 + 입력 + 버튼이 섞인 종합 폼.

    확인 포인트:
    - 한 메시지에 여러 ``processid``가 공존할 때 callback payload 구조
    - mandatory 검증이 모든 필드를 한 번에 검사하는가
    - 컨트롤 간 세로 간격이 자연스러운가
    """

    return [
        prod_blocks.add_text("📋 회의실 예약", color="#0066cc", align="center"),
        prod_blocks.add_select(
            "회의실",
            [("A동 301", "a301"), ("A동 401", "a401"), ("B동 502", "b502")],
            processid="SelectRoom",
            required=True,
            alertmsg="회의실을 선택해 주세요.",
        ),
        prod_blocks.add_datetimepicker(
            "시작 시각",
            processid="SelectDateTime",
            default="2026/05/01 14:00",
            required=True,
            alertmsg="시각을 선택해 주세요.",
        ),
        prod_blocks.add_input(
            "참석 인원",
            processid="InputCount",
            placeholder="숫자 입력",
            max_length=3,
            required=True,
            alertmsg="참석 인원을 입력해 주세요.",
        ),
        prod_blocks.add_button(
            "예약",
            processid="SendButton",
            value="reserve",
            bgcolor="#0066cc",
            textcolor="#ffffff",
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
    # devtools/blocks.py 기반 (standalone)
    "text_baseline": "단순 한 줄 텍스트 (sanity check)",
    "label_basics": "라벨 색상/정렬/bgcolor 렌더링",
    "column_widths": "컬럼 너비(%, px, auto) 분배",
    "grid_table": "bodystyle=grid 표 렌더링",
    "approval_buttons": "버튼 + confirmmsg + 콜백 (raw cell)",
    "hyperlink_card": "하이퍼링크 + opengraph",
    # api.cube.rich_blocks 기반 (production helpers)
    "buttons_basic": "production add_button — bgcolor/confirmmsg/clickurl",
    "radio_choice": "단일 선택 라디오 그룹 (add_choice multi=False)",
    "checkbox_choice": "다중 선택 체크박스 (add_choice multi=True)",
    "select_dropdown": "드롭다운 선택 (add_select)",
    "input_field": "단일 행 입력 + 길이 검증 (add_input)",
    "textarea_field": "다중 행 입력 (add_textarea)",
    "datepicker_basic": "날짜 선택 (add_datepicker)",
    "datetimepicker_basic": "날짜+시간 선택 (add_datetimepicker)",
    "image_basic": "이미지 카드 (add_image, displaytype=resize)",
    "mixed_form": "select + datetime + input + button 종합 폼",
}

_FACTORIES: dict[str, Callable[[], list[Any]]] = {
    "text_baseline": text_baseline,
    "label_basics": label_basics,
    "column_widths": column_widths,
    "grid_table": grid_table,
    "approval_buttons": approval_buttons,
    "hyperlink_card": hyperlink_card,
    "buttons_basic": buttons_basic,
    "radio_choice": radio_choice,
    "checkbox_choice": checkbox_choice,
    "select_dropdown": select_dropdown,
    "input_field": input_field,
    "textarea_field": textarea_field,
    "datepicker_basic": datepicker_basic,
    "datetimepicker_basic": datetimepicker_basic,
    "image_basic": image_basic,
    "mixed_form": mixed_form,
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
