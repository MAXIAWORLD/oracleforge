import asyncio
import httpx
from core.config import settings
from services.aws_bedrock_client import aws_bedrock_client


class ProxyForwarder:
    @staticmethod
    async def forward_openai(
        request_body: dict, api_key: str, timeout_s: float = 60.0
    ) -> dict:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                json=request_body,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            return resp.json()

    @staticmethod
    async def forward_anthropic(
        request_body: dict, api_key: str, timeout_s: float = 60.0
    ) -> dict:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                json=request_body,
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            return resp.json()

    @staticmethod
    async def forward_google(
        request_body: dict, api_key: str, timeout_s: float = 60.0
    ) -> dict:
        """Google Gemini via their OpenAI-compatible endpoint."""
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            resp = await client.post(
                "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
                json=request_body,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            return resp.json()

    @staticmethod
    async def forward_deepseek(
        request_body: dict, api_key: str, timeout_s: float = 60.0
    ) -> dict:
        """DeepSeek via their OpenAI-compatible endpoint."""
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            resp = await client.post(
                "https://api.deepseek.com/v1/chat/completions",
                json=request_body,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            return resp.json()

    @staticmethod
    async def forward_openai_stream(
        request_body: dict, api_key: str, timeout_s: float = 120.0
    ):
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            async with client.stream(
                "POST",
                "https://api.openai.com/v1/chat/completions",
                json=request_body,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            ) as resp:
                resp.raise_for_status()
                async for chunk in resp.aiter_bytes():
                    yield chunk

    @staticmethod
    async def forward_anthropic_stream(
        request_body: dict, api_key: str, timeout_s: float = 120.0
    ):
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            async with client.stream(
                "POST",
                "https://api.anthropic.com/v1/messages",
                json=request_body,
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
            ) as resp:
                resp.raise_for_status()
                async for chunk in resp.aiter_bytes():
                    yield chunk

    @staticmethod
    async def forward_google_stream(
        request_body: dict, api_key: str, timeout_s: float = 120.0
    ):
        """Google Gemini OpenAI-compat streaming."""
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            async with client.stream(
                "POST",
                "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
                json=request_body,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            ) as resp:
                resp.raise_for_status()
                async for chunk in resp.aiter_bytes():
                    yield chunk

    @staticmethod
    async def forward_deepseek_stream(
        request_body: dict, api_key: str, timeout_s: float = 120.0
    ):
        """DeepSeek OpenAI-compat streaming."""
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            async with client.stream(
                "POST",
                "https://api.deepseek.com/v1/chat/completions",
                json=request_body,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            ) as resp:
                resp.raise_for_status()
                async for chunk in resp.aiter_bytes():
                    yield chunk

    @staticmethod
    async def forward_openrouter(
        request_body: dict, api_key: str, timeout_s: float = 60.0
    ) -> dict:
        """OpenRouter via their OpenAI-compatible endpoint."""
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                json=request_body,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://llmbudget.maxiaworld.app",  # Required by OpenRouter
                    "X-Title": "BudgetForge",  # Optional but recommended
                },
            )
            resp.raise_for_status()
            return resp.json()

    @staticmethod
    async def forward_openrouter_stream(
        request_body: dict, api_key: str, timeout_s: float = 120.0
    ):
        """OpenRouter streaming via OpenAI-compatible endpoint."""
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            async with client.stream(
                "POST",
                "https://openrouter.ai/api/v1/chat/completions",
                json=request_body,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://budgetforge.io",
                    "X-Title": "BudgetForge",
                },
            ) as resp:
                resp.raise_for_status()
                async for chunk in resp.aiter_bytes():
                    yield chunk

    @staticmethod
    async def forward_together(
        request_body: dict, api_key: str, timeout_s: float = 60.0
    ) -> dict:
        """Together AI via leur endpoint OpenAI-compatible."""
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            resp = await client.post(
                "https://api.together.xyz/v1/chat/completions",
                json=request_body,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            return resp.json()

    @staticmethod
    async def forward_together_stream(
        request_body: dict, api_key: str, timeout_s: float = 120.0
    ):
        """Together AI streaming via OpenAI-compatible endpoint."""
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            async with client.stream(
                "POST",
                "https://api.together.xyz/v1/chat/completions",
                json=request_body,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            ) as resp:
                resp.raise_for_status()
                async for chunk in resp.aiter_bytes():
                    yield chunk

    @staticmethod
    async def forward_azure_openai(
        request_body: dict, api_key: str, timeout_s: float = 60.0
    ) -> dict:
        """Azure OpenAI via leur endpoint OpenAI-compatible."""
        from fastapi import HTTPException

        base_url = settings.azure_openai_base_url
        if not base_url:
            raise HTTPException(
                status_code=400,
                detail="AZURE_OPENAI_BASE_URL not configured on this server",
            )
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            resp = await client.post(
                f"{base_url}/openai/deployments/{request_body.get('model', 'gpt-4o')}/chat/completions?api-version=2024-02-15-preview",
                json=request_body,
                headers={"api-key": api_key, "Content-Type": "application/json"},
            )
            resp.raise_for_status()
            return resp.json()

    @staticmethod
    async def forward_azure_openai_stream(
        request_body: dict, api_key: str, timeout_s: float = 120.0
    ):
        """Azure OpenAI streaming via leur endpoint OpenAI-compatible."""
        from fastapi import HTTPException

        base_url = settings.azure_openai_base_url
        if not base_url:
            raise HTTPException(
                status_code=400,
                detail="AZURE_OPENAI_BASE_URL not configured on this server",
            )
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            async with client.stream(
                "POST",
                f"{base_url}/openai/deployments/{request_body.get('model', 'gpt-4o')}/chat/completions?api-version=2024-02-15-preview",
                json=request_body,
                headers={"api-key": api_key, "Content-Type": "application/json"},
            ) as resp:
                resp.raise_for_status()
                async for chunk in resp.aiter_bytes():
                    yield chunk

    @staticmethod
    async def forward_ollama(request_body: dict) -> dict:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{settings.ollama_base_url}/api/chat",
                json={**request_body, "stream": False},
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            return resp.json()

    @staticmethod
    async def forward_ollama_stream(request_body: dict, timeout_s: float = 120.0):
        """Streaming natif Ollama — retourne des chunks newline-JSON."""
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            async with client.stream(
                "POST",
                f"{settings.ollama_base_url}/api/chat",
                json={**request_body, "stream": True},
                headers={"Content-Type": "application/json"},
            ) as resp:
                resp.raise_for_status()
                async for chunk in resp.aiter_bytes():
                    yield chunk

    @staticmethod
    async def forward_ollama_openai_compat(
        request_body: dict, api_key: str = "", timeout_s: float = 60.0
    ) -> dict:
        """Endpoint OpenAI-compatible d'Ollama (/v1/chat/completions)."""
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            resp = await client.post(
                f"{settings.ollama_base_url}/v1/chat/completions",
                json=request_body,
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            return resp.json()

    @staticmethod
    async def forward_ollama_openai_compat_stream(
        request_body: dict, api_key: str = "", timeout_s: float = 120.0
    ):
        """Streaming OpenAI-compatible via Ollama — retourne des chunks SSE."""
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            async with client.stream(
                "POST",
                f"{settings.ollama_base_url}/v1/chat/completions",
                json=request_body,
                headers={"Content-Type": "application/json"},
            ) as resp:
                resp.raise_for_status()
                async for chunk in resp.aiter_bytes():
                    yield chunk

    @staticmethod
    async def forward_aws_bedrock(
        request_body: dict, api_key: str = "", timeout_s: float = 60.0
    ) -> dict:
        """B5.2/B5.6 (C05, H18): AWS Bedrock via API Converse, wrappé dans asyncio.to_thread."""
        from fastapi import HTTPException

        # B5.6 (H18): 503 propre si non configuré (pas ValueError)
        if not aws_bedrock_client.is_configured():
            raise HTTPException(status_code=503, detail="AWS Bedrock not configured")

        model = request_body.get("model", "anthropic.claude-v2")
        messages = request_body.get("messages", [])
        temperature = request_body.get("temperature", 0.7)
        max_tokens = request_body.get("max_tokens", 1000)

        def _sync_call():
            converse_response = aws_bedrock_client.invoke_model_converse(
                model, messages, temperature=temperature, max_tokens=max_tokens
            )
            return aws_bedrock_client.convert_from_converse_response(
                converse_response, model
            )

        # B5.2 (C05): wrappé dans to_thread pour ne pas bloquer l'event loop async
        return await asyncio.to_thread(_sync_call)

    @staticmethod
    async def forward_aws_bedrock_stream(
        request_body: dict, api_key: str = "", timeout_s: float = 120.0
    ):
        """AWS Bedrock streaming non supporté."""
        from fastapi import HTTPException

        raise HTTPException(
            status_code=501,
            detail="AWS Bedrock streaming is not supported. Use non-streaming mode.",
        )
