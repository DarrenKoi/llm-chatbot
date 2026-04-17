"""블록 팩토리와 의도 스키마의 통합 데모.

실행:
    python doc/sample_codes/demo_compose.py

목적:
    - rich_blocks의 함수들이 규격에 맞는 JSON을 생성하는지 눈으로 검증한다.
    - intent_schema -> Block 변환(translator)의 참조 구현을 제공한다.
    - 애매한 규격 항목은 상단 UNCERTAIN 목록에 정리한다.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# 샘플 디렉터리를 import 경로에 추가 (프로젝트 설치 없이 실행 가능하게)
sys.path.insert(0, str(Path(__file__).resolve().parent))

from intent_schema import (  # noqa: E402
    BlockIntent,
    ChoiceIntent,
    ChoiceOption,
    DatePickerIntent,
    ImageIntent,
    InputIntent,
    ReplyIntent,
    TableIntent,
    TextIntent,
)
from rich_blocks import (  # noqa: E402
    Block,
    build_richnotification,
    choice_block,
    datepicker_block,
    image_block,
    input_block,
    table_block,
    text_block,
)


# ---------------------------------------------------------------------------
# 규격 확인이 필요한 항목
# ---------------------------------------------------------------------------
#
# 1. popupoption 문자열 포맷 — rule.txt에 열거값이 없음. 실제 Cube 예시 샘플
#    (richnotification_samples.md)에서 사용례를 확인해야 한다.
# 2. image.displaytype 기본값 — "none"/"crop"/"resize" 중 어느 것이 기본인지
#    불명. 현재 샘플은 "resize"로 설정.
# 3. image.location vs image.inner — location은 이미지 자체 저장소, inner는
#    linkurl 대상 DMZ 여부로 해석. 운영 이미지 URL 패턴으로 재확인 필요.
# 4. process.processtype / processdata 사용 맥락 — 빈 문자열 기본이나, 특정
#    워크플로(승인/반려 등)에서 어떤 값이 필요한지 확인 필요.
# 5. content[].header — 규격상 `{}` 기본이지만, 다중 content 항목 시 실제
#    쓰임새가 있는지 샘플로 확인 필요.
# 6. fromusername이 정확히 5개가 아닐 때 Cube 서버가 오류를 내는지, 공백을
#    허용하는지 실측 필요.
# 7. mandatory가 inputtext.minlength/maxlength 검증과 중복될 때 우선순위가
#    어떻게 동작하는지 확인 필요.


# ---------------------------------------------------------------------------
# intent -> Block 변환 (translator 참조 구현)
# ---------------------------------------------------------------------------


def intent_to_block(intent: BlockIntent) -> Block:
    """한 개의 의도 객체를 Block 하나로 변환한다."""
    if isinstance(intent, TextIntent):
        return text_block(intent.text)
    if isinstance(intent, TableIntent):
        # 제목이 있으면 제목 텍스트 블록 + 표 블록 병합이 아니라, 여기서는 표만.
        # 제목은 reply 단계에서 별도 TextIntent로 프롬프트해도 된다.
        return table_block(intent.headers, intent.rows)
    if isinstance(intent, ImageIntent):
        return image_block(intent.source_url, intent.alt, linkurl=intent.link_url)
    if isinstance(intent, ChoiceIntent):
        return choice_block(
            intent.question,
            [(opt.label, opt.value) for opt in intent.options],
            processid=intent.processid,
            multi=intent.multi,
            required=intent.required,
        )
    if isinstance(intent, InputIntent):
        return input_block(
            intent.label,
            processid=intent.processid,
            placeholder=intent.placeholder,
            min_length=intent.min_length,
            max_length=intent.max_length,
            required=intent.required,
        )
    if isinstance(intent, DatePickerIntent):
        return datepicker_block(
            intent.label,
            processid=intent.processid,
            default=intent.default,
            required=intent.required,
        )
    raise TypeError(f"Unknown intent kind: {type(intent).__name__}")


def reply_to_blocks(reply: ReplyIntent) -> list[Block]:
    return [intent_to_block(b) for b in reply.blocks]


# ---------------------------------------------------------------------------
# 데모 시나리오
# ---------------------------------------------------------------------------


def demo_text_only() -> dict:
    """시나리오 1: 단순 안내 텍스트."""
    return build_richnotification(
        text_block("안녕하세요. 무엇을 도와드릴까요?"),
        from_id="X905552",
        token="BOT_TOKEN_PLACEHOLDER",
        from_usernames=["챗봇", "ChatBot", "チャットボット", "聊天机器人", ""],
        user_id="2067928",
        channel_id="CH_0001",
    )


def demo_table() -> dict:
    """시나리오 2: LLM이 표를 생성했을 때."""
    return build_richnotification(
        text_block("2026년 3월 근태 현황입니다.", align="left"),
        table_block(
            headers=["일자", "근무", "연차", "비고"],
            rows=[
                ["03-02", "O", "", ""],
                ["03-03", "O", "", ""],
                ["03-04", "", "반차(오후)", "병원"],
                ["03-05", "O", "", ""],
            ],
        ),
        from_id="X905552",
        token="BOT_TOKEN_PLACEHOLDER",
        from_usernames=["HR봇", "HRBot", "", "", ""],
        user_id="2067928",
        channel_id="CH_0001",
    )


def demo_choice_callback() -> dict:
    """시나리오 3: 사용자에게 선택을 요청 + 콜백 수신."""
    return build_richnotification(
        text_block("여행 유형을 선택해 주세요."),
        choice_block(
            "여행 유형",
            [("국내 출장", "domestic"), ("해외 출장", "overseas"), ("사내 워크숍", "workshop")],
            processid="Sentence",
            multi=False,
            required=True,
            alertmsg="여행 유형을 선택해 주세요.",
        ),
        datepicker_block("출발일", processid="SelectDate", required=True),
        input_block(
            "목적",
            processid="Sentence1",
            placeholder="간단히 입력",
            min_length=1,
            max_length=200,
            required=True,
        ),
        from_id="X905552",
        token="BOT_TOKEN_PLACEHOLDER",
        from_usernames=["여행봇", "TravelBot", "", "", ""],
        user_id="2067928",
        channel_id="CH_0001",
        callback_address="http://10.158.121.214:17614/chatbot/chat/cube",
        session_id="Bot_Travel_0001",
        sequence="1",
    )


def demo_via_intent_schema() -> dict:
    """시나리오 4: LLM 의도 객체를 가정하고 translator로 변환."""
    llm_reply = ReplyIntent(
        blocks=[
            TextIntent(text="추천 드리는 작업 3가지입니다."),
            ChoiceIntent(
                question="어떤 작업부터 진행할까요?",
                options=[
                    ChoiceOption(label="월간 보고서 초안", value="report"),
                    ChoiceOption(label="일정 정리", value="schedule"),
                    ChoiceOption(label="회의록 요약", value="minutes"),
                ],
                processid="Sentence",
                multi=False,
            ),
        ],
        needs_callback=True,
    )
    blocks = reply_to_blocks(llm_reply)
    return build_richnotification(
        *blocks,
        from_id="X905552",
        token="BOT_TOKEN_PLACEHOLDER",
        from_usernames=["업무봇", "WorkBot", "", "", ""],
        user_id="2067928",
        channel_id="CH_0001",
        callback_address="http://10.158.121.214:17614/chatbot/chat/cube",
        session_id="Bot_Work_0001",
    )


def demo_image() -> dict:
    """시나리오 5: 이미지 전송."""
    return build_richnotification(
        text_block("요청하신 차트입니다."),
        image_block(
            source_url="10.158.122.138/Resource/Image/chart_2026_03.png",
            alt="2026년 3월 근태 차트",
            width="100%",
            displaytype="resize",
            location=True,
            inner=True,
        ),
        from_id="X905552",
        token="BOT_TOKEN_PLACEHOLDER",
        from_usernames=["리포트봇", "ReportBot", "", "", ""],
        user_id="2067928",
        channel_id="CH_0001",
    )


# ---------------------------------------------------------------------------
# 실행 엔트리
# ---------------------------------------------------------------------------


def _dump(title: str, payload: dict) -> None:
    print(f"\n{'=' * 20} {title} {'=' * 20}")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    _dump("1. 텍스트만", demo_text_only())
    _dump("2. 표", demo_table())
    _dump("3. 선택+날짜+입력 (콜백 포함)", demo_choice_callback())
    _dump("4. 의도 스키마 → 변환", demo_via_intent_schema())
    _dump("5. 이미지", demo_image())
