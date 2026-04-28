"""dev 측 의도 판별 유틸 (mirror of api/workflows/intent_utils.py).

이 파일은 ``api/workflows/intent_utils.py``의 mirror 사본이다. ``HARNESS.md``의
"api/ ↔ devtools/ 격리 정책"에 따라 두 파일을 같은 PR에서 함께 업데이트해야 한다.
정지 발화 마커 집합이 한쪽에서만 늘어나면 dev/prod 동작이 달라지므로 주의.
"""

import re

_NON_WORD_PATTERN = re.compile(r"[\W_]+", flags=re.UNICODE)
_STOP_CONVERSATION_MARKERS = {
    "bye",
    "byebye",
    "cancel",
    "done",
    "end",
    "exit",
    "goodbye",
    "nothanks",
    "nothankyou",
    "quit",
    "stop",
    "stopit",
    "thanksbye",
    "thankyoubye",
    "thanksdone",
    "thankyoudone",
    "그만",
    "그만할게",
    "그만할래",
    "끝",
    "끝낼게",
    "끝내자",
    "여기까지",
    "이제그만",
    "이제끝",
    "종료",
    "중지",
    "취소",
    "됐어",
    "됐습니다",
    "됐어요",
    "괜찮아",
    "괜찮아요",
    "고마워됐어",
    "감사해요됐어요",
    "감사합니다됐습니다",
    "바이",
    "빠이",
    "잘가",
}


def is_stop_conversation_message(message: str) -> bool:
    """대화를 정중히 마치려는 짧은 발화인지 판별한다."""

    normalized = _NON_WORD_PATTERN.sub("", message.strip().lower())
    if not normalized:
        return False
    return normalized in _STOP_CONVERSATION_MARKERS
