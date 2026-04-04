"""AI chat handler using the Anthropic API."""

from __future__ import annotations

import logging
from typing import Any

from .config import AI_MODEL, ANTHROPIC_API_KEY, MAX_HISTORY_TURNS, MAX_TOKENS

logger = logging.getLogger("chemeng.ai")

_client = None


def _get_client():
    """Lazy-initialize the Anthropic client."""
    global _client
    if _client is not None:
        return _client

    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")

    try:
        import anthropic
    except ImportError:
        raise RuntimeError("anthropic package is not installed. Run: pip install anthropic")

    _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


class ChemEngAssistant:
    """Wrapper around the Anthropic API for ChemEng help chat."""

    def __init__(self) -> None:
        self._system_prompt: str | None = None

    def _get_system_prompt(self) -> str:
        if self._system_prompt is None:
            try:
                from core import get_registry

                from .prompts.system import build_system_prompt

                registry = get_registry()
                skills = registry.list_skills()
                self._system_prompt = build_system_prompt(skills)
            except Exception:
                from .prompts.system import build_system_prompt
                self._system_prompt = build_system_prompt(None)
        return self._system_prompt

    def chat(
        self,
        message: str,
        history: list[dict[str, str]] | None = None,
        context: dict[str, Any] | None = None,
    ) -> str:
        """Send a message and return the assistant's reply.

        Args:
            message: The user's message.
            history: Previous conversation turns [{"role": "user"|"assistant", "content": "..."}].
            context: Optional context (current_skill, last_result).

        Returns:
            The assistant's text reply.
        """
        client = _get_client()
        system_prompt = self._get_system_prompt()

        if context:
            context_note = "\n\n## Current context\n"
            if context.get("current_skill"):
                context_note += f"- User is viewing the **{context['current_skill']}** calculation tab.\n"
            if context.get("last_result"):
                context_note += f"- Last calculation result summary: {context['last_result']}\n"
            system_prompt += context_note

        messages: list[dict[str, str]] = []
        if history:
            truncated = history[-MAX_HISTORY_TURNS * 2:]
            for h in truncated:
                if h.get("role") in ("user", "assistant") and h.get("content"):
                    messages.append({"role": h["role"], "content": h["content"]})

        messages.append({"role": "user", "content": message})

        try:
            response = client.messages.create(
                model=AI_MODEL,
                max_tokens=MAX_TOKENS,
                system=system_prompt,
                messages=messages,
            )
            if not response.content:
                return "No response generated. Please try again."
            return response.content[0].text
        except Exception as e:
            logger.error("AI chat error: %s", e)
            raise
