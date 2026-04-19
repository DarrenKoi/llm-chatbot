"""LLM이 채우는 의도(intent) 스키마.

`doc/richnotification_전송_전략.md` 하이브리드 설계의 LLM 측 인터페이스다.
LLM은 richnotification 원본 JSON을 절대 보지 않고, 여기 정의된 작은
discriminated union만 채워 반환한다. translator.intent_to_block()이 이
의도를 rich_blocks.Block으로 변환한다.

Pydantic v2 BaseModel을 사용해 LangChain `with_structured_output` /
tool calling과 직접 호환되도록 한다.

참조: doc/sample_codes/intent_schema.py (dataclass 버전)
"""

from typing import Annotated, Literal

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


BlockIntent = Annotated[
    TextIntent | TableIntent | ImageIntent | ChoiceIntent | InputIntent | DatePickerIntent,
    Field(discriminator="kind"),
]


class ReplyIntent(BaseModel):
    """LLM이 반환하는 최종 응답 형태.

    blocks가 전부 TextIntent 뿐이라면 multimessage로 보낼 수 있다.
    한 개라도 구조적 블록이면 richnotification으로 승격한다.
    """

    blocks: list[BlockIntent] = Field(default_factory=list)
    needs_callback: bool = False
