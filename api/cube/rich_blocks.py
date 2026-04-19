"""richnotification 블록 팩토리·컴포저.

`doc/richnotification_전송_전략.md` 단계 1a의 Python 측 스키마 권한자.
LLM은 이 모듈을 직접 호출하지 않는다. 워크플로 코드(또는 translator)가
의도 객체를 받아 여기 블록 팩토리를 호출해 Cube 규격 JSON을 만든다.

규약:
    - 모든 텍스트 배열은 5개 언어(한/영/일/중/기타) 길이를 강제한다(_lang5).
    - 색상은 hex 문자열 또는 빈 문자열.
    - 날짜/시간은 문자열. "YYYY/MM/DD", "YYYY/MM/DD HH:MM".

규격 원문: doc/richnotification_rule.txt
참조 구현: doc/sample_codes/rich_blocks.py
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Literal

LANG_COUNT = 5
SYSTEM_REQUEST_IDS = (
    "cubeuniquename",
    "cubechannelid",
    "cubeaccountid",
    "cubelanguagetype",
    "cubemessageid",
)


# ---------------------------------------------------------------------------
# 내부 헬퍼
# ---------------------------------------------------------------------------


def _lang5(text: str | list[str]) -> list[str]:
    """문자열을 5개 언어 배열로 확장한다."""
    if isinstance(text, list):
        padded = list(text) + [""] * LANG_COUNT
        return padded[:LANG_COUNT]
    return [text, "", "", "", ""]


def _row(
    columns: list[dict],
    *,
    align: str = "left",
    width: str = "100%",
    border: bool = False,
    bgcolor: str = "",
) -> dict:
    return {
        "bgcolor": bgcolor,
        "border": border,
        "align": align,
        "width": width,
        "column": columns,
    }


def _column(
    *,
    type: str,
    control: dict,
    width: str = "100%",
    align: str = "left",
    valign: str = "middle",
    border: bool = False,
    bgcolor: str = "",
) -> dict:
    return {
        "bgcolor": bgcolor,
        "border": border,
        "align": align,
        "valign": valign,
        "width": width,
        "type": type,
        "control": control,
    }


# ---------------------------------------------------------------------------
# 블록 자료구조
# ---------------------------------------------------------------------------


@dataclass
class Block:
    """블록 하나가 생성하는 row 목록과 부가 메타데이터."""

    rows: list[dict]
    mandatory: list[dict] = field(default_factory=list)
    requestid: list[str] = field(default_factory=list)
    bodystyle: Literal["none", "grid"] = "none"


# ---------------------------------------------------------------------------
# 블록 팩토리
# ---------------------------------------------------------------------------


def text_block(
    text: str | list[str],
    *,
    color: str = "#000000",
    align: Literal["left", "center", "right"] = "left",
) -> Block:
    """4.1 Label — 정적 텍스트 출력."""
    control = {
        "active": True,
        "text": _lang5(text),
        "color": color,
    }
    return Block(rows=[_row([_column(type="label", control=control, align=align)], align=align)])


def button_block(
    text: str | list[str],
    *,
    processid: str = "SendButton",
    value: str = "",
    confirmmsg: str = "",
    bgcolor: str = "",
    textcolor: str = "",
    clickurl: str = "",
    sso: bool = False,
    inner: bool = False,
    align: Literal["left", "center", "right"] = "center",
) -> Block:
    """4.2 Button — 클릭 가능한 액션 버튼."""
    control = {
        "processid": processid,
        "active": True,
        "text": _lang5(text),
        "confirmmsg": confirmmsg,
        "value": value,
        "bgcolor": bgcolor,
        "textcolor": textcolor,
        "align": align,
        "clickurl": clickurl,
        "androidurl": "",
        "iosurl": "",
        "popupoption": "",
        "sso": sso,
        "inner": inner,
    }
    return Block(
        rows=[_row([_column(type="button", control=control, align=align)], align=align)],
        requestid=[processid],
    )


def choice_block(
    question: str | list[str],
    options: list[tuple[str, str]],
    *,
    processid: str = "Sentence",
    multi: bool = False,
    default_value: str | None = None,
    required: bool = False,
    alertmsg: str | list[str] = "",
) -> Block:
    """4.3 Radio / 4.4 Checkbox — 단일/다중 선택.

    같은 processid를 공유하는 radio 여러 개가 단일 선택 그룹을 이룬다.
    checkbox도 같은 processid면 다중 선택 묶음이다.
    """
    control_type = "checkbox" if multi else "radio"
    rows: list[dict] = []

    rows.append(
        _row(
            [
                _column(
                    type="label",
                    control={"active": True, "text": _lang5(question), "color": "#000000"},
                )
            ]
        )
    )

    for label, value in options:
        checked = default_value is not None and default_value == value
        rows.append(
            _row(
                [
                    _column(
                        type=control_type,
                        control={
                            "processid": processid,
                            "active": True,
                            "text": _lang5(label),
                            "value": value,
                            "checked": checked,
                        },
                    )
                ]
            )
        )

    mandatory: list[dict] = []
    if required:
        mandatory.append(
            {
                "processid": processid,
                "alertmsg": _lang5(alertmsg or question),
            }
        )

    return Block(rows=rows, mandatory=mandatory, requestid=[processid])


def input_block(
    label: str | list[str],
    *,
    processid: str = "Sentence",
    placeholder: str | list[str] = "",
    default: str = "",
    min_length: int = -1,
    max_length: int = -1,
    width: str = "100%",
    validmsg: str | list[str] = "",
    required: bool = False,
    alertmsg: str | list[str] = "",
) -> Block:
    """4.5 InputText — 단일 행 텍스트 입력."""
    control = {
        "processid": processid,
        "active": True,
        "text": _lang5(label),
        "value": default,
        "width": width,
        "minlength": min_length,
        "maxlength": max_length,
        "placeholder": _lang5(placeholder),
        "validmsg": _lang5(validmsg),
    }
    mandatory: list[dict] = []
    if required:
        mandatory.append(
            {
                "processid": processid,
                "alertmsg": _lang5(alertmsg or label),
            }
        )
    return Block(
        rows=[_row([_column(type="inputtext", control=control)])],
        mandatory=mandatory,
        requestid=[processid],
    )


def textarea_block(
    label: str | list[str],
    *,
    processid: str = "Comment",
    placeholder: str | list[str] = "",
    default: str = "",
    min_length: int = -1,
    max_length: int = -1,
    width: str = "100%",
    height: str = "100px",
    validmsg: str | list[str] = "",
    required: bool = False,
    alertmsg: str | list[str] = "",
) -> Block:
    """4.6 Textarea — 여러 행 텍스트 입력."""
    control = {
        "processid": processid,
        "active": True,
        "text": _lang5(label),
        "value": default,
        "width": width,
        "height": height,
        "minlength": min_length,
        "maxlength": max_length,
        "placeholder": _lang5(placeholder),
        "validmsg": _lang5(validmsg),
    }
    mandatory: list[dict] = []
    if required:
        mandatory.append(
            {
                "processid": processid,
                "alertmsg": _lang5(alertmsg or label),
            }
        )
    return Block(
        rows=[_row([_column(type="textarea", control=control)])],
        mandatory=mandatory,
        requestid=[processid],
    )


def select_block(
    label: str | list[str],
    options: list[tuple[str, str]],
    *,
    processid: str = "SelectContent",
    default_value: str | None = None,
    required: bool = False,
    alertmsg: str | list[str] = "",
) -> Block:
    """4.7 Select — 드롭다운 선택."""
    items = [
        {
            "text": _lang5(opt_label),
            "value": value,
            "selected": (default_value is not None and default_value == value),
        }
        for opt_label, value in options
    ]
    control = {
        "processid": processid,
        "active": True,
        "text": _lang5(label),
        "item": items,
    }
    mandatory: list[dict] = []
    if required:
        mandatory.append(
            {
                "processid": processid,
                "alertmsg": _lang5(alertmsg or label),
            }
        )
    return Block(
        rows=[_row([_column(type="select", control=control)])],
        mandatory=mandatory,
        requestid=[processid],
    )


def datepicker_block(
    label: str | list[str],
    *,
    processid: str = "SelectDate",
    default: str = "",
    required: bool = False,
    alertmsg: str | list[str] = "",
) -> Block:
    """4.8 DatePicker — 날짜 선택. default 포맷 "YYYY/MM/DD"."""
    control = {
        "processid": processid,
        "active": True,
        "text": _lang5(label),
        "value": default,
    }
    mandatory: list[dict] = []
    if required:
        mandatory.append(
            {
                "processid": processid,
                "alertmsg": _lang5(alertmsg or label),
            }
        )
    return Block(
        rows=[_row([_column(type="datepicker", control=control)])],
        mandatory=mandatory,
        requestid=[processid],
    )


def datetimepicker_block(
    label: str | list[str],
    *,
    processid: str = "SelectDateTime",
    default: str = "",
    required: bool = False,
    alertmsg: str | list[str] = "",
) -> Block:
    """4.9 DateTimePicker — 날짜+시간 선택. default 포맷 "YYYY/MM/DD HH:MM"."""
    control = {
        "processid": processid,
        "active": True,
        "text": _lang5(label),
        "value": default,
    }
    mandatory: list[dict] = []
    if required:
        mandatory.append(
            {
                "processid": processid,
                "alertmsg": _lang5(alertmsg or label),
            }
        )
    return Block(
        rows=[_row([_column(type="datetimepicker", control=control)])],
        mandatory=mandatory,
        requestid=[processid],
    )


def image_block(
    source_url: str,
    alt: str | list[str] = "",
    *,
    linkurl: str = "",
    width: str = "100%",
    height: str = "",
    displaytype: Literal["none", "crop", "resize"] = "resize",
    location: bool = True,
    inner: bool = True,
    sso: bool = False,
    popupoption: str = "",
) -> Block:
    """4.10 Image — 이미지 표시.

    location: 이미지 저장 위치가 DMZ 내부인지.
    inner: 클릭 시 이동할 linkurl이 DMZ 내부인지.
    """
    control = {
        "active": True,
        "text": _lang5(alt),
        "linkurl": linkurl,
        "androidurl": "",
        "iosurl": "",
        "popupoption": popupoption,
        "location": location,
        "sourceurl": source_url,
        "displaytype": displaytype,
        "width": width,
        "height": height,
        "sso": sso,
        "inner": inner,
    }
    return Block(rows=[_row([_column(type="image", control=control)])])


def hypertext_block(
    text: str | list[str],
    linkurl: str,
    *,
    inner: bool = False,
    sso: bool = False,
    opengraph: bool = True,
    popupoption: str = "",
) -> Block:
    """4.13 HyperText — 클릭 가능한 링크 텍스트."""
    control = {
        "active": True,
        "text": _lang5(text),
        "linkurl": linkurl,
        "androidurl": "",
        "iosurl": "",
        "popupoption": popupoption,
        "sso": sso,
        "inner": inner,
        "opengraph": opengraph,
    }
    return Block(rows=[_row([_column(type="hypertext", control=control)])])


def table_block(
    headers: list[str],
    rows: list[list[str]],
    *,
    header_bgcolor: str = "#c4c4c4",
    row_bgcolor: str = "#ffffff",
    border: bool = True,
) -> Block:
    """표 — grid bodystyle에서 label 열들로 구성."""
    col_count = max(len(headers), max((len(r) for r in rows), default=0))
    if col_count == 0:
        return Block(rows=[], bodystyle="grid")
    col_width = f"{100 // col_count}%"

    def _make_cell(text: str, *, is_header: bool) -> dict:
        return _column(
            type="label",
            control={"active": True, "text": _lang5(text), "color": "#000000"},
            width=col_width,
            align="center" if is_header else "left",
            border=border,
            bgcolor=header_bgcolor if is_header else row_bgcolor,
        )

    table_rows: list[dict] = []
    header_cells = [_make_cell(headers[i] if i < len(headers) else "", is_header=True) for i in range(col_count)]
    table_rows.append(_row(header_cells, border=border, bgcolor=header_bgcolor))

    for row_data in rows:
        body_cells = [_make_cell(row_data[i] if i < len(row_data) else "", is_header=False) for i in range(col_count)]
        table_rows.append(_row(body_cells, border=border, bgcolor=row_bgcolor))

    return Block(rows=table_rows, bodystyle="grid")


# ---------------------------------------------------------------------------
# 컴포지션
# ---------------------------------------------------------------------------


def compose_content_item(
    *blocks: Block,
    callback_address: str = "",
    session_id: str = "",
    sequence: str = "1",
    summary: str | list[str] = "",
    processdata: str = "",
    processtype: str = "",
) -> dict:
    """여러 Block을 하나의 content[] 항목으로 합친다."""
    all_rows: list[dict] = []
    all_mandatory: list[dict] = []
    all_requestid: list[str] = []
    bodystyle: Literal["none", "grid"] = "none"

    for block in blocks:
        all_rows.extend(block.rows)
        all_mandatory.extend(block.mandatory)
        all_requestid.extend(block.requestid)
        if block.bodystyle == "grid":
            bodystyle = "grid"

    merged_requestid = list(dict.fromkeys([*all_requestid, *SYSTEM_REQUEST_IDS]))

    return {
        "header": {},
        "body": {
            "bodystyle": bodystyle,
            "row": all_rows,
        },
        "process": {
            "callbacktype": "url" if callback_address else "",
            "callbackaddress": callback_address,
            "processdata": processdata,
            "processtype": processtype,
            "summary": _lang5(summary),
            "session": {
                "sessionid": session_id,
                "sequence": sequence,
            },
            "mandatory": all_mandatory,
            "requestid": merged_requestid,
        },
    }


def build_envelope(
    content_items: Iterable[dict],
    *,
    from_id: str,
    token: str,
    from_usernames: Iterable[str],
    user_id: str,
    channel_id: str,
) -> dict:
    """봉투(richnotification 최상위)를 생성한다.

    content_items는 compose_content_item()이 만든 dict의 리스트다.
    봇 자격 증명은 호출자(payload.py)가 config에서 주입한다.
    """
    return {
        "richnotification": {
            "header": {
                "from": from_id,
                "token": token,
                "fromusername": _lang5(list(from_usernames)),
                "to": {
                    "uniquename": [user_id],
                    "channelid": [channel_id],
                },
            },
            "content": list(content_items),
            "result": "",
        }
    }
