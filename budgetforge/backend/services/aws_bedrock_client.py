import boto3
import logging
from botocore.exceptions import ClientError
from typing import Any

from core.config import settings  # B5.1: import absolu (était: from ..core.config)

logger = logging.getLogger(__name__)


class AWSBedrockClient:
    """Client AWS Bedrock utilisant l'API Converse unifiée."""

    def __init__(self):
        self.client = None
        self._initialize_client()

    def _initialize_client(self):
        if not settings.aws_bedrock_access_key or not settings.aws_bedrock_secret_key:
            return
        try:
            self.client = boto3.client(
                "bedrock-runtime",
                aws_access_key_id=settings.aws_bedrock_access_key,
                aws_secret_access_key=settings.aws_bedrock_secret_key,
                region_name=settings.aws_bedrock_region,
            )
        except Exception as e:
            logger.error("Erreur initialisation AWS Bedrock: %s", e)
            self.client = None

    def is_configured(self) -> bool:
        return bool(
            self.client is not None
            and settings.aws_bedrock_access_key
            and settings.aws_bedrock_secret_key
        )

    # B5.3/B5.5: API Converse unifiée — pas de format prompt custom par modèle
    def convert_to_converse_messages(self, messages: list) -> list:
        """Convertit les messages OpenAI au format Converse (liste + system séparé)."""
        result = []
        for msg in messages:
            role = msg.get("role", "user")
            if role == "system":
                continue  # system passé séparément dans invoke_model_converse
            content = msg.get("content", "")
            if isinstance(content, str):
                result.append({"role": role, "content": [{"text": content}]})
            elif isinstance(content, list):
                # Multi-modal: extraire le texte
                text_parts = [
                    p["text"] for p in content if isinstance(p, dict) and "text" in p
                ]
                if text_parts:
                    result.append(
                        {"role": role, "content": [{"text": " ".join(text_parts)}]}
                    )
            else:
                result.append({"role": role, "content": [{"text": str(content)}]})
        return result

    def _extract_system_prompt(self, messages: list) -> list:
        """Extrait les messages system pour le paramètre system de converse."""
        return [
            {"text": msg.get("content", "")}
            for msg in messages
            if msg.get("role") == "system" and msg.get("content")
        ]

    def invoke_model_converse(
        self,
        model_id: str,
        messages: list,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> dict:
        """B5.3 (C06): appel via API Converse unifiée (remplace invoke_model dépréciée).

        Retourne la réponse Converse brute (à convertir via convert_from_converse_response).
        """
        if not self.is_configured():
            raise ValueError("AWS Bedrock non configuré")

        converse_messages = self.convert_to_converse_messages(messages)
        system_blocks = self._extract_system_prompt(messages)

        params: dict[str, Any] = {
            "modelId": model_id,
            "messages": converse_messages,
            "inferenceConfig": {
                "maxTokens": max_tokens,
                "temperature": temperature,
            },
        }
        if system_blocks:
            params["system"] = system_blocks

        try:
            response = self.client.converse(**params)
            return response
        except ClientError as e:
            code = e.response["Error"]["Code"]
            msg = e.response["Error"]["Message"]
            raise Exception(f"AWS Bedrock Error ({code}): {msg}")
        except Exception as e:
            raise Exception(f"Erreur AWS Bedrock: {e}")

    def convert_from_converse_response(
        self, converse_response: dict, model_id: str
    ) -> dict:
        """B5.4 (C02): convertit la réponse Converse en format OpenAI avec vrais tokens."""
        output_message = converse_response.get("output", {}).get("message", {})
        content_blocks = output_message.get("content", [])
        text = " ".join(b.get("text", "") for b in content_blocks if "text" in b)

        usage = converse_response.get("usage", {})
        prompt_tokens = usage.get("inputTokens", 0)
        completion_tokens = usage.get("outputTokens", 0)
        total_tokens = usage.get("totalTokens", prompt_tokens + completion_tokens)

        return {
            "id": f"chatcmpl-bedrock-{id(converse_response)}",
            "object": "chat.completion",
            "created": 0,
            "model": model_id,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": text.strip()},
                    "finish_reason": converse_response.get("stopReason", "stop"),
                }
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            },
        }


# Instance globale
aws_bedrock_client = AWSBedrockClient()
