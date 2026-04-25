"""Amélioration de l'estimation de tokens avec prise en compte de la langue et du type de contenu."""

import re
from typing import Dict, List

# B4.7 (H05): limites réelles par modèle pour clamper max_tokens trop grand
_MODEL_MAX_OUTPUT_TOKENS: dict[str, int] = {
    "gpt-4o": 16_384,
    "gpt-4o-mini": 16_384,
    "gpt-4-turbo": 4_096,
    "gpt-4": 4_096,
    "gpt-3.5-turbo": 4_096,
    "o1": 100_000,
    "o3-mini": 100_000,
    "claude-opus-4-7": 8_192,
    "claude-sonnet-4-6": 8_192,
    "claude-haiku-4-5-20251001": 8_192,
    "claude-haiku-4-5": 8_192,
    "gemini-1.5-pro": 8_192,
    "gemini-1.5-flash": 8_192,
    "gemini-2.0-flash": 8_192,
    "deepseek-chat": 8_192,
    "deepseek-reasoner": 8_192,
    "mistral-large": 4_096,
    "mistral-small": 4_096,
}
_DEFAULT_MAX_OUTPUT_TOKENS = 8_192


class TokenEstimator:
    """Estimateur de tokens amélioré avec facteurs de correction par langue et type de contenu."""

    # Facteurs de correction par langue (basés sur la densité moyenne de tokens)
    LANGUAGE_FACTORS = {
        "english": 1.0,  # Base
        "french": 1.15,  # Français : plus de tokens par caractère
        "spanish": 1.05,  # Espagnol
        "german": 1.2,  # Allemand : mots composés
        "chinese": 0.25,  # Chinois : caractères = mots
        "japanese": 0.3,  # Japonais
        "korean": 0.35,  # Coréen
        "arabic": 0.8,  # Arabe
        "russian": 1.1,  # Russe
        "code": 0.7,  # Code : tokens plus denses
    }

    # Patterns pour détecter le type de contenu (précompilés — évite recompilation + réduit réentrée ReDoS)
    CODE_PATTERNS = [
        re.compile(r"def\s+\w+\s*\("),
        re.compile(r"function\s+\w+\s*\("),
        re.compile(r"class\s+\w+"),
        re.compile(r"import\s+\w+"),
        re.compile(r"from\s+\w+\s+import"),
        re.compile(r"\w+\s*=\s*\w+\s*\("),
        re.compile(r"\$\w+"),
        re.compile(r"<\?php"),
        re.compile(r"<script>"),
        re.compile(r"public\s+class"),
        re.compile(r"private\s+\w+"),
    ]

    @classmethod
    def detect_language(cls, text: str) -> str:
        """Détecte la langue dominante dans le texte."""
        text_lower = text.lower()

        # Détection du code
        for pattern in cls.CODE_PATTERNS:
            if re.search(pattern, text_lower):
                return "code"

        # Détection par fréquence de caractères spécifiques
        char_counts = {}
        for char in text_lower:
            if char.isalpha():
                char_counts[char] = char_counts.get(char, 0) + 1

        # Heuristiques simples pour les langues principales
        if (
            "é" in text_lower
            or "è" in text_lower
            or "ê" in text_lower
            or "à" in text_lower
        ):
            return "french"
        elif "ñ" in text_lower or "¿" in text_lower:
            return "spanish"
        elif (
            "ä" in text_lower
            or "ö" in text_lower
            or "ü" in text_lower
            or "ß" in text_lower
        ):
            return "german"
        elif re.search(r"[\u4e00-\u9fff]", text):  # Caractères chinois
            return "chinese"
        elif re.search(r"[\u3040-\u309f\u30a0-\u30ff]", text):  # Hiragana/Katakana
            return "japanese"
        elif re.search(r"[\uac00-\ud7af]", text):  # Hangul coréen
            return "korean"
        elif re.search(r"[\u0600-\u06ff]", text):  # Arabe
            return "arabic"
        elif re.search(r"[\u0400-\u04ff]", text):  # Cyrillique
            return "russian"

        # Par défaut, anglais
        return "english"

    @classmethod
    def estimate_tokens(cls, text: str, language: str = None) -> int:
        """Estime le nombre de tokens pour un texte donné.

        Args:
            text: Le texte à analyser
            language: Langue spécifique (optionnel, sinon auto-détectée)

        Returns:
            Estimation du nombre de tokens
        """
        if not text:
            return 1  # H1: plancher à 1 — zéro token = bypass du budget check

        # Détection automatique de la langue si non spécifiée
        if language is None:
            language = cls.detect_language(text)

        # Base : estimation caractères → tokens
        char_count = len(text)

        # Estimation de base (pour l'anglais)
        base_tokens = max(1, char_count // 4)

        # Application du facteur de correction pour la langue
        language_factor = cls.LANGUAGE_FACTORS.get(language, 1.0)
        estimated_tokens = int(base_tokens * language_factor)

        # Ajustement pour les textes très courts (overhead de tokenisation)
        if char_count < 20:
            estimated_tokens = max(estimated_tokens, 3)

        return estimated_tokens

    @classmethod
    def estimate_messages_tokens(cls, messages: List[Dict]) -> int:
        """Estime le nombre de tokens pour une liste de messages OpenAI-style.

        Args:
            messages: Liste de messages avec rôle et contenu

        Returns:
            Estimation totale des tokens
        """
        total_tokens = 0

        for message in messages:
            content = message.get("content", "")
            if isinstance(content, list):
                # Gestion des messages multi-modal (texte + images)
                text_parts = [
                    item["text"]
                    for item in content
                    if isinstance(item, dict) and item.get("type") == "text"
                ]
                content_text = " ".join(text_parts)
            else:
                content_text = str(content)

            # Tokens pour le contenu
            total_tokens += cls.estimate_tokens(content_text)

            # Tokens pour le rôle et la structure du message
            total_tokens += 4  # Overhead par message

            # Tokens supplémentaires pour les rôles système
            if message.get("role") == "system":
                total_tokens += 2

        return total_tokens

    @classmethod
    def estimate_input_tokens(cls, payload: Dict) -> int:
        """Estime les tokens d'entrée pour un payload OpenAI-style.

        Args:
            payload: Payload de requête

        Returns:
            Estimation des tokens d'entrée
        """
        messages = payload.get("messages", [])

        # Estimation des tokens des messages
        message_tokens = cls.estimate_messages_tokens(messages)

        # Tokens pour les paramètres de la requête
        param_tokens = 0
        if "max_tokens" in payload:
            param_tokens += 3
        if "temperature" in payload:
            param_tokens += 3
        if "top_p" in payload:
            param_tokens += 3
        if "stop" in payload:
            param_tokens += len(payload["stop"]) * 2

        return message_tokens + param_tokens + 10  # Overhead de la requête

    @classmethod
    def estimate_output_tokens(cls, payload: Dict, conservative: bool = False) -> int:
        """Estime les tokens de sortie.

        Args:
            payload: Payload de requête
            conservative: Si True, utilise une borne haute pour le prebilling
                (protège le budget contre les grandes réponses inattendues).
                Si False (défaut), utilise l'estimation optimiste ×0.75.

        Returns:
            Estimation des tokens de sortie
        """
        max_tokens = payload.get("max_tokens")
        if max_tokens is not None:
            # B4.7 (H05): clamper max_tokens à la limite réelle du modèle
            model = payload.get("model", "")
            cap = _MODEL_MAX_OUTPUT_TOKENS.get(model, _DEFAULT_MAX_OUTPUT_TOKENS)
            return min(max_tokens, cap)

        if conservative:
            # Borne haute : réserve au moins 512 tokens, jusqu'à 4096.
            # Protège le budget sans sur-bloquer les petits calls légitimes.
            input_tokens = cls.estimate_input_tokens(payload)
            return min(4096, max(int(input_tokens * 2), 512))

        input_tokens = cls.estimate_input_tokens(payload)
        return min(4096, int(input_tokens * 0.75))


# Fonctions de compatibilité pour l'export existant
def estimate_input_tokens(payload: dict) -> int:
    """Fonction de compatibilité avec l'interface existante."""
    return TokenEstimator.estimate_input_tokens(payload)


def estimate_output_tokens(payload: dict, conservative: bool = False) -> int:
    """Fonction de compatibilité avec l'interface existante."""
    return TokenEstimator.estimate_output_tokens(payload, conservative=conservative)
