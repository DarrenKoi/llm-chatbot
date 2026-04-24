"""richnotification cell makers and component composers.

Python is the schema authority for Cube richnotification payloads. Callers
build cells with ``make_*`` helpers, group them with ``add_*`` helpers, and
only pass the composed content into the Cube client.
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


def _lang5(text: TextValue) -> list[str]:
    """문자열을 5개 언어 배열로 확장한다."""
    if isinstance(text, list):
        padded = list(text) + [""] * LANG_COUNT
        return padded[:LANG_COUNT]
    return [text, "", "", "", ""]


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


@dataclass
class Block:
    """Rows and process metadata for a richnotification component."""

    rows: list[Row]
    mandatory: list[dict[str, Any]] = field(default_factory=list)
    requestid: list[str] = field(default_factory=list)
    bodystyle: Literal["none", "grid"] = "none"


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
    """4.1 Label cell."""
    return _column(
        type="label",
        control={"active": True, "text": _lang5(text), "color": color},
        width=width,
        align=align,
        valign=valign,
        border=border,
        bgcolor=bgcolor,
    )


def make_button_cell(
    text: TextValue,
    *,
    processid: str = "SendButton",
    value: str = "",
    confirmmsg: str = "",
    bgcolor: str = "",
    textcolor: str = "",
    clickurl: str = "",
    sso: bool = False,
    inner: bool = False,
    width: str = "100%",
    align: Literal["left", "center", "right"] = "center",
    valign: str = "middle",
    border: bool = False,
) -> Cell:
    """4.2 Button cell."""
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
    return _column(
        type="button",
        control=control,
        width=width,
        align=align,
        valign=valign,
        border=border,
        bgcolor=bgcolor,
    )


def make_radio_cell(
    text: TextValue,
    value: str,
    *,
    processid: str = "Sentence",
    checked: bool = False,
    width: str = "100%",
    align: Literal["left", "center", "right"] = "left",
    valign: str = "middle",
    border: bool = False,
    bgcolor: str = "",
) -> Cell:
    """4.3 Radio cell."""
    return _column(
        type="radio",
        control={
            "processid": processid,
            "active": True,
            "text": _lang5(text),
            "value": value,
            "checked": checked,
        },
        width=width,
        align=align,
        valign=valign,
        border=border,
        bgcolor=bgcolor,
    )


def make_checkbox_cell(
    text: TextValue,
    value: str,
    *,
    processid: str = "Sentence",
    checked: bool = False,
    width: str = "100%",
    align: Literal["left", "center", "right"] = "left",
    valign: str = "middle",
    border: bool = False,
    bgcolor: str = "",
) -> Cell:
    """4.4 Checkbox cell."""
    return _column(
        type="checkbox",
        control={
            "processid": processid,
            "active": True,
            "text": _lang5(text),
            "value": value,
            "checked": checked,
        },
        width=width,
        align=align,
        valign=valign,
        border=border,
        bgcolor=bgcolor,
    )


def make_input_cell(
    label: TextValue,
    *,
    processid: str = "Sentence",
    placeholder: TextValue = "",
    default: str = "",
    min_length: int = -1,
    max_length: int = -1,
    width: str = "100%",
    validmsg: TextValue = "",
    align: Literal["left", "center", "right"] = "left",
    valign: str = "middle",
    border: bool = False,
    bgcolor: str = "",
) -> Cell:
    """4.5 InputText cell."""
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
    return _column(
        type="inputtext",
        control=control,
        width=width,
        align=align,
        valign=valign,
        border=border,
        bgcolor=bgcolor,
    )


def make_textarea_cell(
    label: TextValue,
    *,
    processid: str = "Comment",
    placeholder: TextValue = "",
    default: str = "",
    min_length: int = -1,
    max_length: int = -1,
    width: str = "100%",
    height: str = "100px",
    validmsg: TextValue = "",
    align: Literal["left", "center", "right"] = "left",
    valign: str = "middle",
    border: bool = False,
    bgcolor: str = "",
) -> Cell:
    """4.6 Textarea cell."""
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
    return _column(
        type="textarea",
        control=control,
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
    """4.7 Select cell."""
    items = [
        {
            "text": _lang5(opt_label),
            "value": value,
            "selected": default_value is not None and default_value == value,
        }
        for opt_label, value in options
    ]
    control = {
        "processid": processid,
        "active": True,
        "text": _lang5(label),
        "item": items,
    }
    return _column(
        type="select",
        control=control,
        width=width,
        align=align,
        valign=valign,
        border=border,
        bgcolor=bgcolor,
    )


def make_datepicker_cell(
    label: TextValue,
    *,
    processid: str = "SelectDate",
    default: str = "",
    width: str = "100%",
    align: Literal["left", "center", "right"] = "left",
    valign: str = "middle",
    border: bool = False,
    bgcolor: str = "",
) -> Cell:
    """4.8 DatePicker cell. ``default`` format: YYYY/MM/DD."""
    return _column(
        type="datepicker",
        control={"processid": processid, "active": True, "text": _lang5(label), "value": default},
        width=width,
        align=align,
        valign=valign,
        border=border,
        bgcolor=bgcolor,
    )


def make_datetimepicker_cell(
    label: TextValue,
    *,
    processid: str = "SelectDateTime",
    default: str = "",
    width: str = "100%",
    align: Literal["left", "center", "right"] = "left",
    valign: str = "middle",
    border: bool = False,
    bgcolor: str = "",
) -> Cell:
    """4.9 DateTimePicker cell. ``default`` format: YYYY/MM/DD HH:MM."""
    return _column(
        type="datetimepicker",
        control={"processid": processid, "active": True, "text": _lang5(label), "value": default},
        width=width,
        align=align,
        valign=valign,
        border=border,
        bgcolor=bgcolor,
    )


def make_image_cell(
    source_url: str,
    alt: TextValue = "",
    *,
    linkurl: str = "",
    width: str = "100%",
    height: str = "",
    displaytype: Literal["none", "crop", "resize"] = "resize",
    location: bool = True,
    inner: bool = True,
    sso: bool = False,
    popupoption: str = "",
    align: Literal["left", "center", "right"] = "left",
    valign: str = "middle",
    border: bool = False,
    bgcolor: str = "",
) -> Cell:
    """4.10 Image cell."""
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
    return _column(
        type="image",
        control=control,
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
    """4.13 HyperText cell."""
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
    return _column(
        type="hypertext",
        control=control,
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
    """Create a one-row component from prebuilt cells."""
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


def add_button(
    text: TextValue,
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
    return add_row(
        [
            make_button_cell(
                text,
                processid=processid,
                value=value,
                confirmmsg=confirmmsg,
                bgcolor=bgcolor,
                textcolor=textcolor,
                clickurl=clickurl,
                sso=sso,
                inner=inner,
                align=align,
            )
        ],
        align=align,
        requestid=[processid],
    )


def add_choice(
    question: TextValue,
    options: list[tuple[str, str]],
    *,
    processid: str = "Sentence",
    multi: bool = False,
    default_value: str | None = None,
    required: bool = False,
    alertmsg: TextValue = "",
) -> Block:
    """Add a radio or checkbox choice group."""
    cell_maker = make_checkbox_cell if multi else make_radio_cell
    rows = [
        _row(
            [
                make_label_cell(question),
            ]
        )
    ]
    for label, value in options:
        rows.append(
            _row(
                [
                    cell_maker(
                        label,
                        value,
                        processid=processid,
                        checked=default_value is not None and default_value == value,
                    )
                ]
            )
        )
    return Block(
        rows=rows,
        mandatory=_mandatory(processid, required=required, alertmsg=alertmsg, fallback=question),
        requestid=[processid],
    )


def add_input(
    label: TextValue,
    *,
    processid: str = "Sentence",
    placeholder: TextValue = "",
    default: str = "",
    min_length: int = -1,
    max_length: int = -1,
    width: str = "100%",
    validmsg: TextValue = "",
    required: bool = False,
    alertmsg: TextValue = "",
) -> Block:
    return add_row(
        [
            make_input_cell(
                label,
                processid=processid,
                placeholder=placeholder,
                default=default,
                min_length=min_length,
                max_length=max_length,
                width=width,
                validmsg=validmsg,
            )
        ],
        mandatory=_mandatory(processid, required=required, alertmsg=alertmsg, fallback=label),
        requestid=[processid],
    )


def add_textarea(
    label: TextValue,
    *,
    processid: str = "Comment",
    placeholder: TextValue = "",
    default: str = "",
    min_length: int = -1,
    max_length: int = -1,
    width: str = "100%",
    height: str = "100px",
    validmsg: TextValue = "",
    required: bool = False,
    alertmsg: TextValue = "",
) -> Block:
    return add_row(
        [
            make_textarea_cell(
                label,
                processid=processid,
                placeholder=placeholder,
                default=default,
                min_length=min_length,
                max_length=max_length,
                width=width,
                height=height,
                validmsg=validmsg,
            )
        ],
        mandatory=_mandatory(processid, required=required, alertmsg=alertmsg, fallback=label),
        requestid=[processid],
    )


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


def add_datepicker(
    label: TextValue,
    *,
    processid: str = "SelectDate",
    default: str = "",
    required: bool = False,
    alertmsg: TextValue = "",
) -> Block:
    return add_row(
        [make_datepicker_cell(label, processid=processid, default=default)],
        mandatory=_mandatory(processid, required=required, alertmsg=alertmsg, fallback=label),
        requestid=[processid],
    )


def add_datetimepicker(
    label: TextValue,
    *,
    processid: str = "SelectDateTime",
    default: str = "",
    required: bool = False,
    alertmsg: TextValue = "",
) -> Block:
    return add_row(
        [make_datetimepicker_cell(label, processid=processid, default=default)],
        mandatory=_mandatory(processid, required=required, alertmsg=alertmsg, fallback=label),
        requestid=[processid],
    )


def add_image(
    source_url: str,
    alt: TextValue = "",
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
    return add_row(
        [
            make_image_cell(
                source_url,
                alt,
                linkurl=linkurl,
                width=width,
                height=height,
                displaytype=displaytype,
                location=location,
                inner=inner,
                sso=sso,
                popupoption=popupoption,
            )
        ]
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
    """Compose several blocks into one richnotification ``content`` item."""
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
