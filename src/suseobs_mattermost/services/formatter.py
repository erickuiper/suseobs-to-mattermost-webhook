"""Safe template rendering for Mattermost markdown text."""

from __future__ import annotations

import re
from string import Template

from suseobs_mattermost.models.normalized import NormalizedAlert

_MUSTACHE = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def render_message(template_str: str, alert: NormalizedAlert) -> str:
    """
    Substitute ``{{ name }}`` placeholders, then ``$name`` / ``${name}`` via string.Template.
    Uses safe_substitute only — no code execution.
    """
    data = alert.as_template_dict()

    def mustache_repl(match: re.Match[str]) -> str:
        key = match.group(1)
        return data.get(key, match.group(0))

    text = _MUSTACHE.sub(mustache_repl, template_str)
    return Template(text).safe_substitute(**data)
