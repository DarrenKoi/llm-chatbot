from api import config

DEFAULT_SYSTEM_PROMPT = "You are ITC OSS (Infra. Tech Center / One Stop Solution) Agent, Answer kindly in Korean."


def get_system_prompt() -> str:
    override = config.LLM_SYSTEM_PROMPT_OVERRIDE.strip()
    return override if override else DEFAULT_SYSTEM_PROMPT
