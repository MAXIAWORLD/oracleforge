"""Langchain Chat wrapper for BudgetForge API - Version simplifiée."""

import asyncio
import json
from typing import Any, Dict, Iterator, List, Optional

# Import compatible avec différentes versions de Langchain
try:
    # Nouvelle version (langchain-core)
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.callbacks import CallbackManagerForLLMRun
    from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
    from langchain_core.outputs import ChatResult, ChatGeneration
except ImportError:
    # Ancienne version
    from langchain.chat_models.base import BaseChatModel
    from langchain.callbacks.manager import CallbackManagerForLLMRun
    from langchain.schema.messages import BaseMessage, HumanMessage, AIMessage
    from langchain.schema.output import ChatResult, ChatGeneration

from pydantic import Field


class BudgetForgeChat(BaseChatModel):
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

    @property
    def _llm_type(self) -> str:
        return "budgetforge-chat"

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Synchronous chat generation."""
        return asyncio.run(self._agenerate(messages, stop, run_manager, **kwargs))

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Asynchronous chat generation."""
        import httpx

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # Convert Langchain messages to OpenAI format
        formatted_messages = []
        for message in messages:
            if isinstance(message, HumanMessage):
                formatted_messages.append({"role": "user", "content": message.content})
            elif isinstance(message, AIMessage):
                formatted_messages.append(
                    {"role": "assistant", "content": message.content}
                )
            else:
                # Handle system messages and other types
                formatted_messages.append(
                    {"role": "user", "content": str(message.content)}
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
            content = result["choices"][0]["message"]["content"]

            generation = ChatGeneration(
                message=AIMessage(content=content),
                generation_info=result.get("usage", {}),
            )

            return ChatResult(generations=[generation])

    def stream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[ChatGeneration]:
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
            if isinstance(message, HumanMessage):
                formatted_messages.append({"role": "user", "content": message.content})
            elif isinstance(message, AIMessage):
                formatted_messages.append(
                    {"role": "assistant", "content": message.content}
                )
            else:
                formatted_messages.append(
                    {"role": "user", "content": str(message.content)}
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
                                yield ChatGeneration(
                                    message=AIMessage(content=accumulated_content),
                                    generation_info={"streaming": True},
                                )
                    except (json.JSONDecodeError, KeyError):
                        continue

    def get_num_tokens(self, text: str) -> int:
        """Estimate number of tokens in text."""
        return max(len(text) // 4, 1)

    def get_num_tokens_from_messages(self, messages: List[BaseMessage]) -> int:
        """Estimate tokens from messages."""
        total = 0
        for message in messages:
            total += self.get_num_tokens(str(message.content))
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
