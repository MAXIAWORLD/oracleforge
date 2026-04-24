import boto3
from botocore.exceptions import ClientError
from typing import Dict, Any
import json
from ..core.config import settings


class AWSBedrockClient:
    """Client pour interagir avec AWS Bedrock"""

    def __init__(self):
        self.client = None
        self._initialize_client()

    def _initialize_client(self):
        """Initialise le client AWS Bedrock"""
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
            print(f"Erreur initialisation AWS Bedrock: {e}")
            self.client = None

    def is_configured(self) -> bool:
        """Vérifie si AWS Bedrock est configuré"""
        return (
            self.client is not None
            and settings.aws_bedrock_access_key
            and settings.aws_bedrock_secret_key
        )

    def invoke_model(self, model_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
        """Invoque un modèle Bedrock"""
        if not self.is_configured():
            raise ValueError("AWS Bedrock non configuré")

        try:
            response = self.client.invoke_model(modelId=model_id, body=json.dumps(body))

            response_body = json.loads(response["body"].read())
            return response_body

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            error_message = e.response["Error"]["Message"]
            raise Exception(f"AWS Bedrock Error ({error_code}): {error_message}")

        except Exception as e:
            raise Exception(f"Erreur AWS Bedrock: {str(e)}")

    def convert_to_bedrock_format(
        self, messages: list, temperature: float = 0.7, max_tokens: int = 1000
    ) -> Dict[str, Any]:
        """Convertit le format OpenAI en format Bedrock"""
        # Pour Claude sur Bedrock
        if "claude" in messages[0].get("content", "").lower():
            return self._convert_to_claude_format(messages, temperature, max_tokens)

        # Pour LLaMA sur Bedrock
        elif "llama" in messages[0].get("content", "").lower():
            return self._convert_to_llama_format(messages, temperature, max_tokens)

        # Format par défaut (Claude)
        else:
            return self._convert_to_claude_format(messages, temperature, max_tokens)

    def _convert_to_claude_format(
        self, messages: list, temperature: float, max_tokens: int
    ) -> Dict[str, Any]:
        """Convertit en format Claude (Anthropic)"""
        prompt = ""
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                prompt += f"\n\nHuman: {content}"
            elif role == "user":
                prompt += f"\n\nHuman: {content}"
            elif role == "assistant":
                prompt += f"\n\nAssistant: {content}"

        prompt += "\n\nAssistant:"

        return {
            "prompt": prompt,
            "max_tokens_to_sample": max_tokens,
            "temperature": temperature,
            "stop_sequences": ["\n\nHuman:"],
        }

    def _convert_to_llama_format(
        self, messages: list, temperature: float, max_tokens: int
    ) -> Dict[str, Any]:
        """Convertit en format LLaMA"""
        prompt = ""
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                prompt += (
                    f"<|start_header_id|>system<|end_header_id|>\n\n{content}<|eot_id|>"
                )
            elif role == "user":
                prompt += (
                    f"<|start_header_id|>user<|end_header_id|>\n\n{content}<|eot_id|>"
                )
            elif role == "assistant":
                prompt += f"<|start_header_id|>assistant<|end_header_id|>\n\n{content}<|eot_id|>"

        prompt += "<|start_header_id|>assistant<|end_header_id|>\n\n"

        return {"prompt": prompt, "max_gen_len": max_tokens, "temperature": temperature}

    def convert_from_bedrock_format(
        self, bedrock_response: Dict[str, Any], model_id: str
    ) -> Dict[str, Any]:
        """Convertit la réponse Bedrock en format OpenAI"""
        if "claude" in model_id.lower():
            return self._convert_from_claude_format(bedrock_response)
        elif "llama" in model_id.lower():
            return self._convert_from_llama_format(bedrock_response)
        else:
            return self._convert_from_claude_format(bedrock_response)

    def _convert_from_claude_format(
        self, bedrock_response: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Convertit depuis le format Claude"""
        completion = bedrock_response.get("completion", "")

        return {
            "id": f"chatcmpl-{id(bedrock_response)}",
            "object": "chat.completion",
            "created": 0,
            "model": "claude",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": completion.strip()},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }

    def _convert_from_llama_format(
        self, bedrock_response: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Convertit depuis le format LLaMA"""
        generation = bedrock_response.get("generation", "")

        return {
            "id": f"chatcmpl-{id(bedrock_response)}",
            "object": "chat.completion",
            "created": 0,
            "model": "llama",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": generation.strip()},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }


# Instance globale
aws_bedrock_client = AWSBedrockClient()
