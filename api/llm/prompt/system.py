from api import config

SYSTEM_PROMPT_KEY = "system.default"

DEFAULT_SYSTEM_PROMPT = "You are ITC OSS (Infra. Tech Center / One Stop Solution) Agent, Answer kindly in Korean."

_DEFAULT_PROMPTS = {
    SYSTEM_PROMPT_KEY: DEFAULT_SYSTEM_PROMPT,
}


def get_prompt(name: str) -> str:
    if name == SYSTEM_PROMPT_KEY:
        override_prompt = config.LLM_SYSTEM_PROMPT_OVERRIDE.strip()
        if override_prompt:
            return override_prompt

    return _DEFAULT_PROMPTS.get(name, "").strip()


def get_system_prompt() -> str:
    return get_prompt(SYSTEM_PROMPT_KEY)
