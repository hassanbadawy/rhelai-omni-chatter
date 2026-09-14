"""Deterministic blocked-term rail.

Keyword blocking must NOT rely on the self-check LLM judge: a 3B model is
probabilistic and will let rephrasings through. This action is exact and
auditable - edit BLOCKED_TERMS to change policy.
"""
import re
from nemoguardrails.actions import action

BLOCKED_TERMS = [
    # entertainment / off-topic
    "movie", "movies", "film", "netflix", "cinema",
    # weapons / explosives
    "weapon", "weapons", "gun", "guns", "firearm", "rifle", "pistol",
    "bomb", "bombs", "explosive", "explosives", "grenade", "ammunition",
]

# Word-boundary match so "bomb" does not fire on "bombard" unless listed.
_PATTERN = re.compile(r"\b(" + "|".join(re.escape(t) for t in BLOCKED_TERMS) + r")\b", re.I)


@action(is_system_action=True)
async def check_blocked_terms(context: dict = None):
    """Return True when the user message contains a blocked term."""
    text = (context or {}).get("user_message") or ""
    return bool(_PATTERN.search(text))
