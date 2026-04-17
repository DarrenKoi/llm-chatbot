"""richnotification 블록 팩토리 샘플.

본 파일은 `doc/richnotification_전송_전략.md`의 1단계 설계를 검증하기 위한
독립 실행 샘플이다. `api/` 트리의 실제 코드에는 영향을 주지 않는다.

역할:
    - richnotification JSON 규격을 Python이 책임지고 생성한다.
    - LLM은 이 모듈을 직접 호출하지 않는다. 상위 orchestrator가 LLM의 의도 객체
      (intent_schema.py 참고)를 받아 여기의 블록 팩토리를 호출한다.

규약:
    - 모든 텍스트 배열은 5개 언어(한/영/일/중/기타) 길이를 강제한다(_lang5).
    - 색상은 hex 문자열 또는 빈 문자열.
    - 날짜/시간은 문자열. "YYYY/MM/DD", "YYYY/MM/DD HH:MM".

규격 원문: /richnotification_rule.txt
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Literal

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
    """문자열을 5개 언어 배열로 확장한다.

    한국어 슬롯(인덱스 0)에 원문을 넣고 나머지는 빈 문자열로 채운다.
    이미 리스트이면 길이를 5로 맞춘다(자르거나 빈 문자열로 패딩).
    """
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
    """블록 하나가 생성하는 row 목록과 부가 메타데이터.

    상위 compose()가 여러 Block을 합쳐 하나의 content[] 항목을 만든다.
    """

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

    같은 processid를 공유하는 radio 여러 개가 단일 선택 그룹을 이룬다(rule 4.3 주석).
    checkbox도 같은 processid면 다중 선택 묶음이다(rule 4.4 주석).
    """
    control_type = "checkbox" if multi else "radio"
    rows: list[dict] = []

    rows.append(
        _row([_column(
            type="label",
            control={"active": True, "text": _lang5(question), "color": "#000000"},
        )])
    )

    for label, value in options:
        checked = (default_value is not None and default_value == value)
        rows.append(
            _row([_column(
                type=control_type,
                control={
                    "processid": processid,
                    "active": True,
                    "text": _lang5(label),
                    "value": value,
                    "checked": checked,
                },
            )])
        )

    mandatory: list[dict] = []
    if required:
        mandatory.append({
            "processid": processid,
            "alertmsg": _lang5(alertmsg or question),
        })

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
        mandatory.append({
            "processid": processid,
            "alertmsg": _lang5(alertmsg or label),
        })
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
        mandatory.append({
            "processid": processid,
            "alertmsg": _lang5(alertmsg or label),
        })
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
        mandatory.append({
            "processid": processid,
            "alertmsg": _lang5(alertmsg or label),
        })
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
        mandatory.append({
            "processid": processid,
            "alertmsg": _lang5(alertmsg or label),
        })
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
        mandatory.append({
            "processid": processid,
            "alertmsg": _lang5(alertmsg or label),
        })
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

    location: 이미지 저장 위치가 DMZ 내부인지 (내부 리소스면 True).
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
    """4.13 HyperText — 클릭 가능한 링크 텍스트.

    opengraph는 규격상 필수 필드다(rule 4.13).
    """
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
    """표 — grid bodystyle에서 label 열들로 구성.

    열 수는 headers와 rows 중 최댓값을 사용하고 부족한 칸은 빈 문자열로 채운다.
    """
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

    # 중복 제거 + 시스템 ID 부가
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


def build_richnotification(
    *blocks: Block,
    from_id: str,
    token: str,
    from_usernames: Iterable[str],
    user_id: str,
    channel_id: str,
    callback_address: str = "",
    session_id: str = "",
    sequence: str = "1",
    summary: str | list[str] = "",
) -> dict:
    """최상위 richnotification 봉투까지 포함한 전체 페이로드를 만든다.

    실제 운영 코드에서는 api.config의 봇 자격 증명을 주입한다.
    본 샘플은 테스트 값을 받을 수 있도록 인자를 열어 둔다.
    """
    content_item = compose_content_item(
        *blocks,
        callback_address=callback_address,
        session_id=session_id,
        sequence=sequence,
        summary=summary,
    )
    usernames = list(from_usernames)
    return {
        "richnotification": {
            "header": {
                "from": from_id,
                "token": token,
                "fromusername": _lang5(usernames),
                "to": {
                    "uniquename": [user_id],
                    "channelid": [channel_id],
                },
            },
            "content": [content_item],
            "result": "",
        }
    }
