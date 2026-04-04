"""사용자 프로필 정규화 모델을 정의한다."""

from dataclasses import dataclass


@dataclass
class UserProfile:
    """프롬프트 주입에 필요한 최소 사용자 프로필 표현이다."""

    user_id: str
    name: str = ""
    team: str = ""
    organization: str = ""
    work_location: str = ""
    role: str = ""
    email: str = ""
    source: str = ""

    def to_prompt_text(self) -> str:
        """LLM 시스템 프롬프트에 바로 붙일 수 있는 짧은 요약을 만든다."""

        lines: list[str] = []
        if self.name:
            lines.append(f"- 이름: {self.name}")
        if self.organization or self.team:
            group_name = " / ".join(part for part in [self.organization, self.team] if part)
            lines.append(f"- 소속: {group_name}")
        if self.work_location:
            lines.append(f"- 근무지: {self.work_location}")
        if self.role:
            lines.append(f"- 직무: {self.role}")
        if self.source:
            lines.append(f"- 프로필 출처: {self.source}")
        return "\n".join(lines)
