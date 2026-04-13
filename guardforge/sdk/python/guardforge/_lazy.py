"""Lazy proxies for OpenAI and Anthropic so the optional deps stay optional.

Importing `from guardforge import OpenAI` should NOT fail if openai is not
installed. The error only surfaces at instantiation time, with a clear
message telling the user to `pip install guardforge[openai]`.
"""

from __future__ import annotations

from typing import Any


class LazyOpenAI:
    """Lazy proxy for the GuardForge-wrapped OpenAI client.

    Constructing this triggers the import of the actual wrapper, which
    in turn requires the `openai` package. If `openai` is missing, a
    helpful ImportError is raised pointing the user to the extras.
    """

    def __new__(cls, *args: Any, **kwargs: Any) -> Any:
        try:
            from guardforge.openai_wrapper import OpenAI as _OpenAI
        except ImportError as exc:
            raise ImportError(
                "GuardForge OpenAI wrapper requires the openai package. "
                "Install it with: pip install guardforge[openai]"
            ) from exc
        return _OpenAI(*args, **kwargs)


class LazyAnthropic:
    """Lazy proxy for the GuardForge-wrapped Anthropic client."""

    def __new__(cls, *args: Any, **kwargs: Any) -> Any:
        try:
            from guardforge.anthropic_wrapper import Anthropic as _Anthropic
        except ImportError as exc:
            raise ImportError(
                "GuardForge Anthropic wrapper requires the anthropic package. "
                "Install it with: pip install guardforge[anthropic]"
            ) from exc
        return _Anthropic(*args, **kwargs)
