"""여행 계획 예제에서 사용하는 규칙 기반 상수와 helper."""

import re

DESTINATION_ALIASES: dict[str, str] = {
    "서울": "서울",
    "seoul": "서울",
    "부산": "부산",
    "busan": "부산",
    "제주": "제주",
    "제주도": "제주",
    "jeju": "제주",
    "도쿄": "도쿄",
    "tokyo": "도쿄",
    "오사카": "오사카",
    "osaka": "오사카",
    "교토": "교토",
    "kyoto": "교토",
    "타이베이": "타이베이",
    "taipei": "타이베이",
    "방콕": "방콕",
    "bangkok": "방콕",
    "싱가포르": "싱가포르",
    "singapore": "싱가포르",
}

STYLE_ALIASES: dict[str, str] = {
    "도시": "도시",
    "city": "도시",
    "휴양": "휴양",
    "힐링": "휴양",
    "휴식": "휴양",
    "relax": "휴양",
    "자연": "자연",
    "nature": "자연",
    "먹거리": "먹거리",
    "맛집": "먹거리",
    "food": "먹거리",
}

COMPANION_ALIASES: dict[str, str] = {
    "혼자": "혼자",
    "solo": "혼자",
    "친구": "친구",
    "friends": "친구",
    "가족": "가족",
    "family": "가족",
    "연인": "연인",
    "커플": "연인",
    "couple": "연인",
}

STYLE_TO_DESTINATIONS: dict[str, list[str]] = {
    "도시": ["서울", "도쿄", "싱가포르"],
    "휴양": ["제주", "방콕", "싱가포르"],
    "자연": ["제주", "교토", "부산"],
    "먹거리": ["오사카", "타이베이", "부산"],
}

DESTINATION_TO_PLACES: dict[str, list[str]] = {
    "서울": ["경복궁", "북촌한옥마을", "성수동", "한강공원"],
    "부산": ["해운대", "광안리", "감천문화마을", "자갈치시장"],
    "제주": ["함덕해변", "성산일출봉", "협재해변", "동문시장"],
    "도쿄": ["시부야", "아사쿠사", "메이지신궁", "긴자"],
    "오사카": ["도톤보리", "오사카성", "우메다", "신세카이"],
    "교토": ["후시미 이나리 신사", "기요미즈데라", "아라시야마", "니시키시장"],
    "타이베이": ["타이베이 101", "중정기념당", "스린 야시장", "용캉제"],
    "방콕": ["왓 아룬", "아이콘시암", "짜뚜짝 시장", "차오프라야 강변"],
    "싱가포르": ["마리나 베이", "가든스 바이 더 베이", "하지 레인", "센토사"],
}

DESTINATION_DEFAULT_STYLE: dict[str, str] = {
    "서울": "도시",
    "부산": "먹거리",
    "제주": "휴양",
    "도쿄": "도시",
    "오사카": "먹거리",
    "교토": "자연",
    "타이베이": "먹거리",
    "방콕": "휴양",
    "싱가포르": "도시",
}

DURATION_PATTERN = re.compile(r"(?:(\d+)\s*박\s*(\d+)\s*일)|(\d+)\s*일")


def _sorted_aliases(aliases: dict[str, str]) -> list[tuple[str, str]]:
    return sorted(aliases.items(), key=lambda item: len(item[0]), reverse=True)


DESTINATION_ALIASES_SORTED = _sorted_aliases(DESTINATION_ALIASES)
STYLE_ALIASES_SORTED = _sorted_aliases(STYLE_ALIASES)
COMPANION_ALIASES_SORTED = _sorted_aliases(COMPANION_ALIASES)


def match_alias(user_message: str, sorted_aliases: list[tuple[str, str]]) -> str:
    """사전 정렬된 별칭 목록에서 첫 번째 매칭 값을 반환한다."""

    lowered = user_message.lower()
    for alias, canonical in sorted_aliases:
        if alias.lower() in lowered:
            return canonical
    return ""


def extract_duration(user_message: str) -> str:
    match = DURATION_PATTERN.search(user_message)
    if not match:
        return ""

    nights, days, days_only = match.groups()
    if nights and days:
        return f"{nights}박 {days}일"
    return f"{days_only}일"


def parse_request(user_message: str) -> tuple[str, str, str, str]:
    normalized = user_message.strip()
    destination = match_alias(normalized, DESTINATION_ALIASES_SORTED)
    travel_style = match_alias(normalized, STYLE_ALIASES_SORTED)
    duration_text = extract_duration(normalized)
    companion_type = match_alias(normalized, COMPANION_ALIASES_SORTED)
    return destination, travel_style, duration_text, companion_type


def recommend_destinations(*, style: str) -> list[str]:
    if style in STYLE_TO_DESTINATIONS:
        return list(STYLE_TO_DESTINATIONS[style])
    return ["서울", "제주", "도쿄"]


def build_companion_note(companion_type: str) -> str:
    if companion_type == "가족":
        return "가족 여행이라면 이동 횟수를 줄이고 휴식 가능한 장소를 중간에 끼워 넣는 편이 좋습니다."
    if companion_type == "연인":
        return "연인 여행이라면 야경이나 산책 코스를 한 구간 넣으면 만족도가 높습니다."
    if companion_type == "친구":
        return "친구 여행이라면 맛집과 야간 활동을 한 구간 포함하면 일정이 덜 단조롭습니다."
    if companion_type == "혼자":
        return "혼자 여행이라면 동선을 단순하게 잡고 오래 머물 곳을 1~2곳 정하는 편이 편합니다."
    return "동행 정보가 없어 일반 여행자 기준으로 무난한 동선으로 추천했습니다."
