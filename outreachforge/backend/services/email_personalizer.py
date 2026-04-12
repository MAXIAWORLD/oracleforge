"""OutreachForge — Email Template Personaliser.

Simple template engine with {variable} interpolation.
In production, this would call an LLM for AI-powered personalisation.
"""

from __future__ import annotations

import re


class _SafeDict(dict):
    def __missing__(self, key: str) -> str:
        return f"{{{key}}}"  # Keep unresolved variables visible


class EmailPersonalizer:
    """Personalise email templates with prospect data."""

    def personalize(
        self,
        template: str,
        prospect: dict,
        extra_vars: dict | None = None,
    ) -> str:
        """Replace {variable} placeholders in template."""
        variables = _SafeDict({
            "name": prospect.get("name", ""),
            "first_name": prospect.get("name", "").split()[0] if prospect.get("name") else "",
            "company": prospect.get("company", ""),
            "title": prospect.get("title", ""),
            "email": prospect.get("email", ""),
        })
        if extra_vars:
            variables.update(extra_vars)
        return template.format_map(variables)

    def validate_template(self, template: str) -> list[str]:
        """Return list of variable names used in template."""
        return re.findall(r"\{(\w+)\}", template)
