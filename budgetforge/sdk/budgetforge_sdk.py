"""BudgetForge SDK simple - Utilisable directement sans installation complexe."""

import asyncio
import json
import httpx
from typing import Dict, List, Optional, Iterator


class BudgetForgeLLM:
    """Client LLM simple pour BudgetForge API."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4",
        provider: str = "openai",
        api_base_url: str = "http://localhost:8000",
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        timeout: int = 30,
    ):
        self.api_key = api_key
        self.model = model
        self.provider = provider
        self.api_base_url = api_base_url
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout = timeout

    async def invoke_async(self, prompt: str, **kwargs) -> str:
        """Appel asynchrone à l'API BudgetForge."""
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

    def invoke(self, prompt: str, **kwargs) -> str:
        """Appel synchrone à l'API BudgetForge."""
        return asyncio.run(self.invoke_async(prompt, **kwargs))

    def stream(self, prompt: str, **kwargs) -> Iterator[str]:
        """Streaming de la réponse."""
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


class BudgetForgeChat:
    """Client Chat simple pour BudgetForge API."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4",
        provider: str = "openai",
        api_base_url: str = "http://localhost:8000",
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        timeout: int = 30,
    ):
        self.api_key = api_key
        self.model = model
        self.provider = provider
        self.api_base_url = api_base_url
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout = timeout

    async def invoke_async(self, messages: List[Dict], **kwargs) -> Dict:
        """Appel asynchrone à l'API BudgetForge."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }

        if self.max_tokens:
            payload["max_tokens"] = self.max_tokens

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

    def invoke(self, messages: List[Dict], **kwargs) -> Dict:
        """Appel synchrone à l'API BudgetForge."""
        return asyncio.run(self.invoke_async(messages, **kwargs))

    def stream(self, messages: List[Dict], **kwargs) -> Iterator[Dict]:
        """Streaming de la réponse."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "stream": True,
            "stream_options": {"include_usage": True},
        }

        if self.max_tokens:
            payload["max_tokens"] = self.max_tokens

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
