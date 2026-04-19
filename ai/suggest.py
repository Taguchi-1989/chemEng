"""AI-powered parameter suggestion for calculation skills."""

from __future__ import annotations

import json
import logging
from typing import Any

from .config import AI_MODEL, ANTHROPIC_API_KEY, MAX_TOKENS

logger = logging.getLogger("chemeng.ai")

_client = None


def _get_client():
    """Lazy-initialize a singleton Anthropic client."""
    global _client
    if _client is None:
        import anthropic
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


def suggest_parameters(
    skill_id: str,
    current_params: dict[str, Any],
    goal: str | None = None,
) -> list[dict[str, Any]]:
    """Suggest optimal parameters for a given skill.

    Args:
        skill_id: The skill identifier (e.g. "distillation").
        current_params: Current form values from the user.
        goal: Optional user-described goal (e.g. "distill ethanol from 10% to 95%").

    Returns:
        List of suggestion dicts: [{"param": str, "value": Any, "reason": str}]
    """
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")

    # Load skill schema
    try:
        from core import get_registry

        registry = get_registry()
        skill = registry.get_skill(skill_id)
        if skill is None:
            return []
        schema_desc = "\n".join(
            f"- {p.name} ({p.type}): {p.description} [unit: {p.unit or 'N/A'}, default: {p.default}]"
            for p in skill.input_schema
        )
        skill_name = skill.name
    except Exception:
        schema_desc = "(Schema not available)"
        skill_name = skill_id

    goal_text = f"\nUser's goal: {goal}" if goal else ""

    prompt = f"""\
You are a chemical engineering expert. Suggest optimal or typical parameter values \
for the "{skill_name}" calculation in ChemEng.

## Skill parameter schema
{schema_desc}

## User's current inputs
{json.dumps(current_params, ensure_ascii=False, default=str)}
{goal_text}

## Instructions
- For each empty or default parameter where you can suggest a better value, provide a suggestion.
- Only suggest parameters that would meaningfully improve the calculation.
- Return a JSON array of objects: {{"param": "parameter_name", "value": <suggested_value>, "reason": "brief explanation"}}
- If no suggestions are needed, return an empty array: []
- Return ONLY the JSON array, no other text.
"""

    client = _get_client()

    try:
        response = client.messages.create(
            model=AI_MODEL,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()

        # Extract JSON from response (handle markdown code blocks)
        if text.startswith("```"):
            lines = text.split("\n")
            json_lines = [line for line in lines if not line.startswith("```")]
            text = "\n".join(json_lines).strip()

        suggestions = json.loads(text)
        if not isinstance(suggestions, list):
            return []
        return suggestions
    except (json.JSONDecodeError, IndexError, KeyError) as e:
        logger.warning("Failed to parse AI suggestion response: %s", e)
        return []
    except Exception as e:
        logger.error("AI suggest error: %s", e)
        raise
