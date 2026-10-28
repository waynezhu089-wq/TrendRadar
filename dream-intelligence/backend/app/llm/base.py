from typing import Protocol

class LLMError(Exception):
    """Safe message only: never include headers, prompts or provider responses."""

class LLMClient(Protocol):
    def analyze(self, messages: list[dict[str, str]]) -> str: ...
