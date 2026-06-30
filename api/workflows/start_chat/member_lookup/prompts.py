# ruff: noqa: E501
"""사내 구성원 조회 노드의 프롬프트·상수를 정의한다."""

# 컨텍스트 블록 머리말 (generate_reply_node가 retrieved_contexts로 LLM에 전달)
MEMBER_CONTEXT_HEADER = "[사내 구성원 정보]"

# 강제 조회 명령어 (memory의 `!` prefix 규약 준수 — Cube는 `/` 예약).
# 접두어를 떼어낸 나머지를 검색어로 사용한다.
COMMAND_TOKENS = ("!담당", "!member", "!누구")

# 매 메시지 LLM 호출을 막기 위한 1차 키워드 게이트(자동 감지 경로).
KEYWORD_GATE = (
    "담당",
    "담당자",
    "누가",
    "누구",
    "연락처",
    "전화",
    "전화번호",
    "내선",
    "부서",
    "팀",
    "소속",
)

MEMBER_LOOKUP_DECISION_SYSTEM_PROMPT = """\
너는 사내 챗봇의 라우터다. 사용자의 메시지가 "사내 구성원(사람)" 또는 "특정 업무의 담당자"를
묻는 질의인지 판단하고, 구성원 검색에 쓸 검색어를 추출한다.

다음 JSON 객체 하나만 출력한다(설명·코드블록 금지):
{
  "needs_lookup": true | false,   // 사람/담당자 관련 질의이면 true
  "mode": "search" | "filter",    // 자유 검색이면 search, 부서/팀 명시 필터이면 filter
  "query": "검색어",                // 이름 또는 업무/직무 키워드 (mode=search일 때 핵심)
  "filters": {                      // mode=filter일 때만 채움. 해당 없으면 빈 객체.
    "dept": "부서명",
    "part": "팀/파트명",
    "text": "추가 자유 검색어"
  }
}

판단 기준:
- "누가 OO 담당이야?", "OO 담당자 알려줘", "OO팀 누구 있어?", "홍길동 연락처" → needs_lookup=true
- 일반 지식/잡담/번역 등 사람과 무관한 질의 → needs_lookup=false (나머지 필드는 빈 값)
- 업무/책임으로 담당자를 찾을 땐 그 업무 키워드를 query에 넣는다. 예: "출하 검사 담당" → query="출하 검사"
"""

MEMBER_LOOKUP_DECISION_USER_PROMPT_PREFIX = "사용자 메시지(JSON):\n"
