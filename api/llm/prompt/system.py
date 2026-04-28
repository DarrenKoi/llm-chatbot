from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from api import config

DEFAULT_SYSTEM_PROMPT = (
    "You are ITC OSS (Infra. Tech Center / One Stop Solution) Agent, Answer kindly in Korean. "
    "모르는 것은 모른다고 답하세요. 확실하지 않은 정보는 추측하지 마세요.\n"
    "\n"
    "[응답 형식 가이드]\n"
    '기본은 평문 텍스트({"blocks":[{"kind":"text", ...}]})이다. 다음 중 하나에 해당할 때만\n'
    "구조 블록으로 승격한다:\n"
    "1) 정확한 레이아웃이 필요할 때 — 표(`table`), 이미지(`image`)\n"
    "2) 사용자 입력이 필요할 때 — 선택(`choice`), 입력(`input`), 날짜(`date`)\n"
    "3) 분할 시 의미가 깨질 때 — 한 메시지에 묶어 보내야 할 때\n"
    "\n"
    "형식 규칙:\n"
    '- fallback 텍스트 응답에서도 최상위는 반드시 {"blocks":[...]} JSON 객체다.\n'
    "- blocks=[...] 같은 할당문, Python dict, 주석, markdown fence를 쓰지 마세요.\n"
    '- 모든 키와 문자열은 큰따옴표를 쓰고, 줄바꿈은 문자열 안에 그대로 넣지 말고 "\\n"으로 표현하세요.\n'
    "\n"
    '예) 단순 답변: {"blocks":[{"kind":"text","text":"안녕하세요. 어떻게 도와드릴까요?"}]}\n'
    "예) 두 가지 옵션 묻기:\n"
    '{"blocks":[\n'
    '  {"kind":"text","text":"어떤 형식으로 받으시겠어요?"},\n'
    '  {"kind":"choice","question":"형식","options":[\n'
    '     {"label":"PDF","value":"pdf"},{"label":"엑셀","value":"xlsx"}],\n'
    '   "processid":"SelectFormat"}\n'
    "]}"
)


def get_system_prompt(*, user_profile_text: str = "") -> str:
    override = config.LLM_SYSTEM_PROMPT_OVERRIDE.strip()
    base_prompt = override if override else DEFAULT_SYSTEM_PROMPT
    sections = [base_prompt, _build_time_context()]

    profile_context = _build_profile_context(user_profile_text)
    if profile_context:
        sections.append(profile_context)

    return "\n\n".join(section for section in sections if section)


def _build_profile_context(user_profile_text: str) -> str:
    profile_text = user_profile_text.strip()
    if not profile_text:
        return ""

    return (
        "[사용자 프로필]\n"
        f"{profile_text}\n\n"
        "이 사용자의 소속과 근무 맥락을 고려해 적절한 workflow와 답변 방식을 선택하세요."
    )


def _build_time_context(now: datetime | None = None) -> str:
    current = now.astimezone(_get_llm_timezone()) if now else datetime.now(_get_llm_timezone())
    utc_offset = current.strftime("%z")
    formatted_offset = f"{utc_offset[:3]}:{utc_offset[3:]}" if len(utc_offset) == 5 else utc_offset
    return (
        "현재 한국 현지 시각은 "
        f"{current.strftime('%Y-%m-%d %H:%M:%S')} "
        f"({config.LLM_TIMEZONE}, UTC{formatted_offset})입니다. "
        "오늘, 내일, 이번 주 같은 상대적 시간 표현은 이 시각을 기준으로 해석하세요. "
        "사용자가 현재 시간이나 날짜를 물으면 이 시각 정보를 그대로 사용해 답하세요."
    )


def _get_llm_timezone() -> ZoneInfo:
    try:
        return ZoneInfo(config.LLM_TIMEZONE)
    except ZoneInfoNotFoundError:
        return ZoneInfo("Asia/Seoul")
