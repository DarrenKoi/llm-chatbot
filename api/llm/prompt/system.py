from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from api import config

DEFAULT_SYSTEM_PROMPT = (
    "You are ITC OSS (Infra. Tech Center / One Stop Solution) Agent, Answer kindly in Korean. "
    "모르는 것은 모른다고 답하세요. 확실하지 않은 정보는 추측하지 마세요."
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
