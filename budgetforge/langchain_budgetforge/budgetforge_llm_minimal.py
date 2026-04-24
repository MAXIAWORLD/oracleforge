"""Langchain LLM wrapper for BudgetForge API - Version minimale."""

import asyncio
import json
from typing import Any, Dict, List, Optional, Iterator

# Import direct sans dépendances complexes
from pydantic import Field


class BudgetForgeLLM:
    """Langchain LLM wrapper for BudgetForge API with budget enforcement."""

    # BudgetForge API configuration
    api_base_url: str = Field(default="https://llmbudget.maxiaworld.app")
    api_key: str = Field(description="BudgetForge project API key")

    # LLM configuration
    model: str = Field(default="gpt-4", description="Target LLM model")
    provider: str = Field(default="openai", description="LLM provider")

    # Budget enforcement
    max_tokens: Optional[int] = Field(
        default=None, description="Maximum tokens per call"
    )
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)

    # Advanced settings
    timeout: int = Field(default=30, description="Request timeout in seconds")

    def __init__(self, **kwargs):
        from pydantic.fields import FieldInfo

        for name in type(self).__annotations__:
            class_val = getattr(type(self), name, None)
            if isinstance(class_val, FieldInfo):
                default = class_val.default
                setattr(self, name, None if default is ... else default)
        for key, value in kwargs.items():
            setattr(self, key, value)

    def invoke(self, prompt: str, **kwargs) -> str:
        """Synchronous call to BudgetForge API."""
        return asyncio.run(self._acall(prompt, **kwargs))

    async def _acall(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> str:
        """Asynchronous call to BudgetForge API."""
        import httpx

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
        }

        if self.max_tokens:
            payload["max_tokens"] = self.max_tokens
        if stop:
            payload["stop"] = stop

        # Merge additional kwargs
        payload.update(kwargs)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.api_base_url}/proxy/{self.provider}/v1/chat/completions",
                headers=headers,
                json=payload,
            )

            if response.status_code != 200:
                error_msg = (
                    f"BudgetForge API error: {response.status_code} - {response.text}"
                )
                raise ValueError(error_msg)

            result = response.json()
            return result["choices"][0]["message"]["content"]

    def stream(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> Iterator[str]:
        """Stream response from BudgetForge API."""
        import httpx

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
            "stream": True,
            "stream_options": {"include_usage": True},
        }

        if self.max_tokens:
            payload["max_tokens"] = self.max_tokens
        if stop:
            payload["stop"] = stop

        payload.update(kwargs)

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.api_base_url}/proxy/{self.provider}/v1/chat/completions",
                headers=headers,
                json=payload,
                stream=True,
            )

            if response.status_code != 200:
                error_msg = (
                    f"BudgetForge API error: {response.status_code} - {response.text}"
                )
                raise ValueError(error_msg)

            for line in response.iter_lines():
                if line.startswith("data: ") and line.strip() != "data: [DONE]":
                    try:
                        data = json.loads(line[6:])
                        if "choices" in data and len(data["choices"]) > 0:
                            delta = data["choices"][0].get("delta", {})
                            if "content" in delta:
                                yield delta["content"]
                    except (json.JSONDecodeError, KeyError):
                        continue

    def get_num_tokens(self, text: str) -> int:
        """Estimate number of tokens in text."""
        # Simple estimation - 4 chars per token
        return max(len(text) // 4, 1)

    @property
    def _identifying_params(self) -> Dict[str, Any]:
        """Get identifying parameters."""
        return {
            "model": self.model,
            "provider": self.provider,
            "api_base_url": self.api_base_url,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
