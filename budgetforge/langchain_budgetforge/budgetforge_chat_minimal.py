"""Langchain Chat wrapper for BudgetForge API - Version minimale."""

import asyncio
import json
from typing import Any, Dict, Iterator, List, Optional

from pydantic import Field


class BudgetForgeChat:
    """Langchain Chat wrapper for BudgetForge API with budget enforcement."""

    # BudgetForge API configuration
    api_base_url: str = Field(default="http://localhost:8000")
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
        for key, value in kwargs.items():
            setattr(self, key, value)

    def invoke(self, messages: List[dict], **kwargs) -> dict:
        """Synchronous chat generation."""
        return asyncio.run(self._agenerate(messages, **kwargs))

    async def _agenerate(
        self,
        messages: List[dict],
        stop: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> dict:
        """Asynchronous chat generation."""
        import httpx

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # Convert Langchain messages to OpenAI format
        formatted_messages = []
        for message in messages:
            if message.get("role") == "user":
                formatted_messages.append(
                    {"role": "user", "content": message.get("content", "")}
                )
            elif message.get("role") == "assistant":
                formatted_messages.append(
                    {"role": "assistant", "content": message.get("content", "")}
                )
            else:
                formatted_messages.append(
                    {"role": "user", "content": str(message.get("content", ""))}
                )

        payload = {
            "model": self.model,
            "messages": formatted_messages,
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
            return {
                "content": result["choices"][0]["message"]["content"],
                "usage": result.get("usage", {}),
            }

    def stream(
        self,
        messages: List[dict],
        stop: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> Iterator[dict]:
        """Stream chat generation."""
        import httpx

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }

        # Convert Langchain messages to OpenAI format
        formatted_messages = []
        for message in messages:
            if message.get("role") == "user":
                formatted_messages.append(
                    {"role": "user", "content": message.get("content", "")}
                )
            elif message.get("role") == "assistant":
                formatted_messages.append(
                    {"role": "assistant", "content": message.get("content", "")}
                )
            else:
                formatted_messages.append(
                    {"role": "user", "content": str(message.get("content", ""))}
                )

        payload = {
            "model": self.model,
            "messages": formatted_messages,
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

            accumulated_content = ""
            for line in response.iter_lines():
                if line.startswith("data: ") and line.strip() != "data: [DONE]":
                    try:
                        data = json.loads(line[6:])
                        if "choices" in data and len(data["choices"]) > 0:
                            delta = data["choices"][0].get("delta", {})
                            if "content" in delta:
                                accumulated_content += delta["content"]
                                yield {
                                    "content": accumulated_content,
                                    "streaming": True,
                                }
                    except (json.JSONDecodeError, KeyError):
                        continue

    def get_num_tokens(self, text: str) -> int:
        """Estimate number of tokens in text."""
        return max(len(text) // 4, 1)

    def get_num_tokens_from_messages(self, messages: List[dict]) -> int:
        """Estimate tokens from messages."""
        total = 0
        for message in messages:
            total += self.get_num_tokens(str(message.get("content", "")))
        return total

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
