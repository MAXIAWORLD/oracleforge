"""OutreachForge — Email Template Personaliser.

Simple template engine with {variable} interpolation.
Uses safe regex replacement — NOT str.format_map() which is vulnerable to SSTI.
"""

from __future__ import annotations

import re


def _safe_interpolate(template: str, variables: dict[str, str]) -> str:
    """Safe template interpolation — only replaces {simple_name} patterns.

    No attribute access ({obj.__class__}), no indexing ({obj[0]}).
    Unresolved variables are kept as-is ({unknown} stays {unknown}).
    """
    def replacer(match: re.Match) -> str:
        key = match.group(1)
        return variables.get(key, match.group(0))  # keep {unknown} visible

    return re.sub(r"\{(\w+)\}", replacer, template)


class EmailPersonalizer:
    """Personalise email templates with prospect data."""

    def personalize(
        self,
        template: str,
        prospect: dict,
        extra_vars: dict | None = None,
    ) -> str:
        """Replace {variable} placeholders in template."""
        variables = {
            "name": prospect.get("name", ""),
            "first_name": prospect.get("name", "").split()[0] if prospect.get("name") else "",
            "company": prospect.get("company", ""),
            "title": prospect.get("title", ""),
            "email": prospect.get("email", ""),
        }
        if extra_vars:
            variables.update(extra_vars)
        return _safe_interpolate(template, variables)

    def validate_template(self, template: str) -> list[str]:
        """Return list of variable names used in template."""
        return re.findall(r"\{(\w+)\}", template)
