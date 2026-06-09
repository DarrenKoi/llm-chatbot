"""LLM이 채우는 의도(intent) 스키마.

`doc/richnotification_전송_전략.md` 하이브리드 설계의 LLM 측 인터페이스다.
LLM은 richnotification 원본 JSON을 절대 보지 않고, 여기 정의된 작은
discriminated union만 채워 반환한다. intent_renderer.intent_to_block()이 이
의도를 rich_blocks.Block으로 변환한다.

Pydantic v2 BaseModel을 사용해 LangChain `with_structured_output` /
tool calling과 직접 호환되도록 한다.

참조: doc/sample_codes/intent_schema.py (dataclass 버전)
"""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field


class TextIntent(BaseModel):
    kind: Literal["text"] = "text"
    text: str


class TableIntent(BaseModel):
    kind: Literal["table"] = "table"
    headers: list[str]
    rows: list[list[str]]
    title: str | None = None


class ImageIntent(BaseModel):
    kind: Literal["image"] = "image"
    source_url: str
    alt: str = ""
    link_url: str = ""


class ChoiceOption(BaseModel):
    label: str
    value: str


class ChoiceIntent(BaseModel):
    kind: Literal["choice"] = "choice"
    question: str
    options: list[ChoiceOption]
    multi: bool = False
    processid: str = "Sentence"
    required: bool = True


class InputIntent(BaseModel):
    kind: Literal["input"] = "input"
    label: str
    placeholder: str = ""
    processid: str = "Sentence"
    min_length: int = -1
    max_length: int = -1
    required: bool = True


class DatePickerIntent(BaseModel):
    kind: Literal["date"] = "date"
    label: str
    default: str = ""
    processid: str = "SelectDate"
    required: bool = True


class ButtonIntent(BaseModel):
    """제출(콜백 트리거) 버튼.

    Cube는 사용자가 버튼 셀을 눌렀을 때만 callbackaddress 로 결과를 POST 한다.
    choice/input/date 같은 입력 블록을 emit 한 응답에는 반드시 ButtonIntent 가
    하나 이상 포함되어야 staged 값이 서버로 돌아온다. 누락된 경우
    intent_renderer 가 기본 "보내기" 버튼을 자동 보강한다.
    """

    kind: Literal["button"] = "button"
    text: str
    processid: str = "SendButton"
    value: str = ""
    confirmmsg: str = ""
    bgcolor: str = ""
    textcolor: str = ""


class RawBlockIntent(BaseModel):
    """추상 BlockIntent로 표현되지 않는 케이스용 escape hatch.

    먼저 새 BlockIntent 타입을 추가할 수 있는지 검토하라(다른 워크플로도 재사용
    가능한지 살피기 위함). 그게 어려운 경우에만 이 escape hatch를 사용해
    ``rich_blocks.py``의 ``add_*``가 만들어내는 row 형식을 그대로 채워 넣는다.

    LLM이 직접 채우는 용도가 아니라 워크플로 코드가 ``WorkflowReply.intents``에
    수동으로 넣는 용도다. 그래서 ``BlockIntent`` 디스크리미네이티드 유니언에는
    포함하지만 시스템 프롬프트의 LLM 가이드에는 노출하지 않는다.
    """

    kind: Literal["raw_block"] = "raw_block"
    rows: list[dict[str, Any]]
    mandatory: list[dict[str, Any]] = Field(default_factory=list)
    requestid: list[str] = Field(default_factory=list)
    bodystyle: Literal["none", "grid"] = "none"


BlockIntent = Annotated[
    TextIntent
    | TableIntent
    | ImageIntent
    | ChoiceIntent
    | InputIntent
    | DatePickerIntent
    | ButtonIntent
    | RawBlockIntent,
    Field(discriminator="kind"),
]


_INTERACTIVE_INTENT_TYPES: tuple[type, ...] = (ChoiceIntent, InputIntent, DatePickerIntent)


def is_interactive_intent(intent: BaseModel) -> bool:
    """사용자 입력을 staged 한 뒤 제출 버튼이 필요한 블록인지 판정.

    RawBlockIntent 는 작성자가 직접 버튼까지 구성하는 escape hatch 이므로
    제외한다. 새 입력형 intent 가 추가되면 _INTERACTIVE_INTENT_TYPES 한 군데만
    수정하면 된다.
    """
    return isinstance(intent, _INTERACTIVE_INTENT_TYPES)


class ReplyIntent(BaseModel):
    """LLM이 반환하는 최종 응답 형태.

    blocks가 전부 TextIntent 뿐이라면 multimessage로 보낼 수 있다.
    한 개라도 구조적 블록이면 richnotification으로 승격한다.
    """

    blocks: list[BlockIntent] = Field(default_factory=list)
    needs_callback: bool = False
