"""의도(intent) -> richnotification Block 렌더러.

LLM 측 의도 객체(api.cube.intents)를 받아 Cube 규격 Block(api.cube.rich_blocks)
으로 변환한다. 봇 자격 증명·콜백 주소 같은 인프라 값은 호출자(payload.py
또는 service.py)가 주입한다.

참조 구현: doc/sample_codes/demo_compose.py:69
"""

from api.cube import rich_blocks
from api.cube.intents import (
    BlockIntent,
    ChoiceIntent,
    DatePickerIntent,
    ImageIntent,
    InputIntent,
    RawBlockIntent,
    TableIntent,
    TextIntent,
)


def intent_to_block(intent: BlockIntent) -> rich_blocks.Block:
    """한 개의 의도 객체를 Block 하나로 변환한다."""
    if isinstance(intent, TextIntent):
        return rich_blocks.add_text(intent.text)
    if isinstance(intent, TableIntent):
        return rich_blocks.add_table(intent.headers, intent.rows)
    if isinstance(intent, ImageIntent):
        return rich_blocks.add_image(intent.source_url, intent.alt, linkurl=intent.link_url)
    if isinstance(intent, ChoiceIntent):
        return rich_blocks.add_choice(
            intent.question,
            [(opt.label, opt.value) for opt in intent.options],
            processid=intent.processid,
            multi=intent.multi,
            required=intent.required,
        )
    if isinstance(intent, InputIntent):
        return rich_blocks.add_input(
            intent.label,
            processid=intent.processid,
            placeholder=intent.placeholder,
            min_length=intent.min_length,
            max_length=intent.max_length,
            required=intent.required,
        )
    if isinstance(intent, DatePickerIntent):
        return rich_blocks.add_datepicker(
            intent.label,
            processid=intent.processid,
            default=intent.default,
            required=intent.required,
        )
    if isinstance(intent, RawBlockIntent):
        return rich_blocks.Block(
            rows=list(intent.rows),
            mandatory=list(intent.mandatory),
            requestid=list(intent.requestid),
            bodystyle=intent.bodystyle,
        )
    raise TypeError(f"Unknown intent kind: {type(intent).__name__}")


def intents_to_blocks(intents: list[BlockIntent]) -> list[rich_blocks.Block]:
    return [intent_to_block(intent) for intent in intents]


def intents_to_history_text(intents: list[BlockIntent]) -> str:
    """대화 기록(conversation history)에 저장하기 위한 텍스트 다이제스트.

    richnotification으로 전송된 구조 블록도 LLM이 다음 턴에서 맥락을 이어갈 수
    있도록, 사람과 LLM 모두 읽을 수 있는 한국어 요약으로 변환한다.
    """

    parts: list[str] = []
    for intent in intents:
        if isinstance(intent, TextIntent):
            text = intent.text.strip()
            if text:
                parts.append(text)
        elif isinstance(intent, TableIntent):
            title = f" {intent.title}" if intent.title else ""
            parts.append(f"[표{title}] 헤더: {', '.join(intent.headers)} ({len(intent.rows)}행)")
        elif isinstance(intent, ImageIntent):
            label = intent.alt or intent.source_url
            parts.append(f"[이미지] {label}")
        elif isinstance(intent, ChoiceIntent):
            options = ", ".join(opt.label for opt in intent.options)
            parts.append(f"[선택지] {intent.question} (옵션: {options})")
        elif isinstance(intent, InputIntent):
            parts.append(f"[입력 요청] {intent.label}")
        elif isinstance(intent, DatePickerIntent):
            parts.append(f"[날짜 선택] {intent.label}")
        elif isinstance(intent, RawBlockIntent):
            parts.append(f"[richnotification 블록] rows={len(intent.rows)}")
    return "\n".join(parts).strip()


def intents_to_content_item(
    intents: list[BlockIntent],
    *,
    callback_address: str = "",
    session_id: str = "",
    sequence: str = "1",
    summary: str | list[str] = "",
) -> dict:
    """의도 리스트를 단일 content[] 항목 dict로 변환한다."""
    blocks = intents_to_blocks(intents)
    return rich_blocks.add_container(
        *blocks,
        callback_address=callback_address,
        session_id=session_id,
        sequence=sequence,
        summary=summary,
    )
