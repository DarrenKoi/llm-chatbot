"""Minimal standalone richnotification block helpers.

These helpers cover the common devtools cases: text rows, grid tables,
hyperlinks, and select callbacks. Production remains the schema authority in
``api.cube.rich_blocks``; this copy is intentionally small and standalone.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, Literal

LANG_COUNT = 5
SYSTEM_REQUEST_IDS = (
    "cubeuniquename",
    "cubechannelid",
    "cubeaccountid",
    "cubelanguagetype",
    "cubemessageid",
)

Cell = dict[str, Any]
Row = dict[str, Any]
TextValue = str | list[str]


@dataclass
class Block:
    """Rows and process metadata for a richnotification component."""

    rows: list[Row]
    mandatory: list[dict[str, Any]] = field(default_factory=list)
    requestid: list[str] = field(default_factory=list)
    bodystyle: Literal["none", "grid"] = "none"


def make_label_cell(
    text: TextValue,
    *,
    color: str = "#000000",
    width: str = "100%",
    align: Literal["left", "center", "right"] = "left",
    valign: str = "middle",
    border: bool = False,
    bgcolor: str = "",
) -> Cell:
    return _column(
        type="label",
        control={"active": True, "text": _lang5(text), "color": color},
        width=width,
        align=align,
        valign=valign,
        border=border,
        bgcolor=bgcolor,
    )


def make_hypertext_cell(
    text: TextValue,
    linkurl: str,
    *,
    inner: bool = False,
    sso: bool = False,
    opengraph: bool = True,
    popupoption: str = "",
    width: str = "100%",
    align: Literal["left", "center", "right"] = "left",
    valign: str = "middle",
    border: bool = False,
    bgcolor: str = "",
) -> Cell:
    return _column(
        type="hypertext",
        control={
            "active": True,
            "text": _lang5(text),
            "linkurl": linkurl,
            "androidurl": "",
            "iosurl": "",
            "popupoption": popupoption,
            "sso": sso,
            "inner": inner,
            "opengraph": opengraph,
        },
        width=width,
        align=align,
        valign=valign,
        border=border,
        bgcolor=bgcolor,
    )


def make_select_cell(
    label: TextValue,
    options: list[tuple[str, str]],
    *,
    processid: str = "SelectContent",
    default_value: str | None = None,
    width: str = "100%",
    align: Literal["left", "center", "right"] = "left",
    valign: str = "middle",
    border: bool = False,
    bgcolor: str = "",
) -> Cell:
    items = [
        {
            "text": _lang5(opt_label),
            "value": value,
            "selected": default_value is not None and default_value == value,
        }
        for opt_label, value in options
    ]
    return _column(
        type="select",
        control={
            "processid": processid,
            "active": True,
            "text": _lang5(label),
            "item": items,
        },
        width=width,
        align=align,
        valign=valign,
        border=border,
        bgcolor=bgcolor,
    )


def add_row(
    cells: Iterable[Cell],
    *,
    align: Literal["left", "center", "right"] = "left",
    width: str = "100%",
    border: bool = False,
    bgcolor: str = "",
    mandatory: Iterable[dict[str, Any]] = (),
    requestid: Iterable[str] = (),
    bodystyle: Literal["none", "grid"] = "none",
) -> Block:
    return Block(
        rows=[_row(list(cells), align=align, width=width, border=border, bgcolor=bgcolor)],
        mandatory=list(mandatory),
        requestid=list(requestid),
        bodystyle=bodystyle,
    )


def add_text(
    text: TextValue,
    *,
    color: str = "#000000",
    align: Literal["left", "center", "right"] = "left",
) -> Block:
    return add_row([make_label_cell(text, color=color, align=align)], align=align)


def add_select(
    label: TextValue,
    options: list[tuple[str, str]],
    *,
    processid: str = "SelectContent",
    default_value: str | None = None,
    required: bool = False,
    alertmsg: TextValue = "",
) -> Block:
    return add_row(
        [make_select_cell(label, options, processid=processid, default_value=default_value)],
        mandatory=_mandatory(processid, required=required, alertmsg=alertmsg, fallback=label),
        requestid=[processid],
    )


def add_table(
    headers: list[str | Cell],
    rows: list[list[str | Cell]],
    *,
    header_bgcolor: str = "#c4c4c4",
    row_bgcolor: str = "#ffffff",
    border: bool = True,
) -> Block:
    """Add a grid table. Plain strings become label cells; dicts are used as cells."""

    col_count = max(len(headers), max((len(row) for row in rows), default=0))
    if col_count == 0:
        return Block(rows=[], bodystyle="grid")

    col_width = f"{100 // col_count}%"

    def coerce_cell(value: str | Cell, *, is_header: bool) -> Cell:
        align = "center" if is_header else "left"
        bgcolor = header_bgcolor if is_header else row_bgcolor
        if isinstance(value, dict):
            return _with_cell_layout(value, width=col_width, align=align, border=border, bgcolor=bgcolor)
        return make_label_cell(
            str(value),
            width=col_width,
            align=align,
            border=border,
            bgcolor=bgcolor,
        )

    table_rows: list[Row] = []
    header_cells = [
        coerce_cell(headers[index] if index < len(headers) else "", is_header=True) for index in range(col_count)
    ]
    table_rows.append(_row(header_cells, border=border, bgcolor=header_bgcolor))

    for row_data in rows:
        body_cells = [
            coerce_cell(row_data[index] if index < len(row_data) else "", is_header=False) for index in range(col_count)
        ]
        table_rows.append(_row(body_cells, border=border, bgcolor=row_bgcolor))

    return Block(rows=table_rows, bodystyle="grid")


def add_container(
    *blocks: Block,
    callback_address: str = "",
    session_id: str = "",
    sequence: str = "1",
    summary: TextValue = "",
    processdata: str = "",
    processtype: str = "",
) -> dict[str, Any]:
    """Compose several blocks into one richnotification content item."""

    all_rows: list[Row] = []
    all_mandatory: list[dict[str, Any]] = []
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


def build_richnotification(
    *blocks: Block,
    from_id: str,
    token: str,
    from_usernames: Iterable[str],
    user_id: str,
    channel_id: str,
    content_items: Iterable[dict[str, Any]] | None = None,
    callback_address: str = "",
    session_id: str = "",
    sequence: str = "1",
    summary: TextValue = "",
) -> dict[str, Any]:
    """Build the complete Cube richnotification payload."""

    if content_items is None:
        content_items = [
            add_container(
                *blocks,
                callback_address=callback_address,
                session_id=session_id,
                sequence=sequence,
                summary=summary,
            )
        ]

    return {
        "richnotification": {
            "header": {
                "from": from_id,
                "token": token,
                "fromusername": _lang5_username(list(from_usernames)),
                "to": {
                    "uniquename": [user_id],
                    "channelid": [channel_id],
                },
            },
            "content": list(content_items),
            "result": "",
        }
    }


def _lang5(text: TextValue) -> list[str]:
    if isinstance(text, list):
        padded = list(text) + [""] * LANG_COUNT
        return padded[:LANG_COUNT]
    return [text, "", "", "", ""]


def _lang5_username(values: list[str]) -> list[str]:
    """fromusername: 단일 값이면 5개 슬롯 모두에 동일하게 채운다."""

    if len(values) == 1:
        return [values[0]] * LANG_COUNT
    padded = values + [""] * LANG_COUNT
    return padded[:LANG_COUNT]


def _row(
    columns: list[Cell],
    *,
    align: str = "left",
    width: str = "100%",
    border: bool = False,
    bgcolor: str = "",
) -> Row:
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
    control: dict[str, Any],
    width: str = "100%",
    align: str = "left",
    valign: str = "middle",
    border: bool = False,
    bgcolor: str = "",
) -> Cell:
    return {
        "bgcolor": bgcolor,
        "border": border,
        "align": align,
        "valign": valign,
        "width": width,
        "type": type,
        "control": control,
    }


def _mandatory(processid: str, *, required: bool, alertmsg: TextValue, fallback: TextValue) -> list[dict[str, Any]]:
    if not required:
        return []
    return [{"processid": processid, "alertmsg": _lang5(alertmsg or fallback)}]


def _with_cell_layout(
    cell: Cell,
    *,
    width: str,
    align: str,
    border: bool,
    bgcolor: str,
    valign: str = "middle",
) -> Cell:
    laid_out = dict(cell)
    laid_out["width"] = width
    laid_out["align"] = align
    laid_out["valign"] = laid_out.get("valign", valign)
    laid_out["border"] = border
    laid_out["bgcolor"] = bgcolor
    return laid_out
