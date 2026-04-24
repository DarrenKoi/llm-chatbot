"""LLM에게 제공할 '의도(intent) 스키마' 샘플.

하이브리드 설계의 핵심: LLM은 richnotification 원본 JSON을 절대 생성하지 않고,
여기 정의된 작은 의도 객체만 반환한다. Intent renderer(demo_compose.py의 intent_to_block)가
이 의도 객체를 rich_blocks.Block으로 변환한다.

주의:
    본 샘플은 표준 라이브러리(dataclass)만 사용하여 집에서도 실행되게 한다.
    실제 `api/` 통합 시에는 pydantic.BaseModel로 바꿔 LangChain structured output과
    자연스럽게 연결한다. 필드 구조와 의미는 동일하게 유지하면 된다.

Pydantic 전환 예시:
    class ChoiceIntent(BaseModel):
        kind: Literal["choice"] = "choice"
        question: str
        options: list[ChoiceOption]
        multi: bool = False
        ...
    BlockIntent = Annotated[Union[TextIntent, ...], Field(discriminator="kind")]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Union


@dataclass
class TextIntent:
    text: str
    kind: Literal["text"] = "text"


@dataclass
class TableIntent:
    headers: list[str]
    rows: list[list[str]]
    title: str | None = None
    kind: Literal["table"] = "table"


@dataclass
class ImageIntent:
    source_url: str
    alt: str = ""
    link_url: str = ""
    kind: Literal["image"] = "image"


@dataclass
class ChoiceOption:
    label: str
    value: str


@dataclass
class ChoiceIntent:
    question: str
    options: list[ChoiceOption]
    multi: bool = False
    processid: str = "Sentence"
    required: bool = True
    kind: Literal["choice"] = "choice"


@dataclass
class InputIntent:
    label: str
    placeholder: str = ""
    processid: str = "Sentence"
    min_length: int = -1
    max_length: int = -1
    required: bool = True
    kind: Literal["input"] = "input"


@dataclass
class DatePickerIntent:
    label: str
    default: str = ""
    processid: str = "SelectDate"
    required: bool = True
    kind: Literal["date"] = "date"


BlockIntent = Union[
    TextIntent,
    TableIntent,
    ImageIntent,
    ChoiceIntent,
    InputIntent,
    DatePickerIntent,
]


@dataclass
class ReplyIntent:
    """LLM이 반환하는 최종 응답 형태.

    blocks가 전부 TextIntent 뿐이라면 multimessage로 보낼 수 있다.
    한 개라도 구조적 블록이면 richnotification으로 승격한다.
    """

    blocks: list[BlockIntent] = field(default_factory=list)
    needs_callback: bool = False


__all__ = [
    "BlockIntent",
    "ChoiceIntent",
    "ChoiceOption",
    "DatePickerIntent",
    "ImageIntent",
    "InputIntent",
    "ReplyIntent",
    "TableIntent",
    "TextIntent",
]
