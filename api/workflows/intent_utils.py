"""워크플로에서 공통으로 사용하는 간단한 의도 판별 유틸."""

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
