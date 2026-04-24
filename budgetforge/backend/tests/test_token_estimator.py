"""Tests pour le nouvel estimateur de tokens amélioré."""

from services.token_estimator import (
    TokenEstimator,
    estimate_input_tokens,
    estimate_output_tokens,
)


class TestTokenEstimator:
    """Tests unitaires pour TokenEstimator."""

    def test_detect_language_english(self):
        """Test la détection de l'anglais."""
        text = "This is a simple English text for testing purposes."
        assert TokenEstimator.detect_language(text) == "english"

    def test_detect_language_french(self):
        """Test la détection du français."""
        text = "Ceci est un texte français avec des caractères accentués: é è ê à"
        assert TokenEstimator.detect_language(text) == "french"

    def test_detect_language_code_python(self):
        """Test la détection du code Python."""
        text = "def hello_world():\n    print('Hello World')"
        assert TokenEstimator.detect_language(text) == "code"

    def test_detect_language_code_javascript(self):
        """Test la détection du code JavaScript."""
        text = "function test() {\n    console.log('test');\n}"
        assert TokenEstimator.detect_language(text) == "code"

    def test_estimate_tokens_english(self):
        """Test l'estimation pour l'anglais."""
        text = "Hello world"  # 11 caractères
        # Base: 11 // 4 = 2.75 → 3 tokens
        # Facteur anglais: 1.0 → 3 tokens
        assert TokenEstimator.estimate_tokens(text) == 3

    def test_estimate_tokens_french(self):
        """Test l'estimation pour le français."""
        text = "Bonjour le monde avec des caractères accentués: é è ê à"  # Texte avec accents
        estimated = TokenEstimator.estimate_tokens(text, "french")
        # Doit être supérieur à l'estimation anglaise pour le même texte
        english_estimate = TokenEstimator.estimate_tokens(text, "english")
        assert estimated > english_estimate
        assert estimated >= 10  # Plage raisonnable

    def test_estimate_tokens_chinese(self):
        """Test l'estimation pour le chinois."""
        text = "你好世界"  # 4 caractères
        estimated = TokenEstimator.estimate_tokens(text, "chinese")
        # Doit être inférieur à l'estimation anglaise pour le même nombre de caractères
        english_text = "abcd"  # 4 caractères anglais
        english_estimate = TokenEstimator.estimate_tokens(english_text, "english")
        # Le facteur chinois (0.25) devrait rendre l'estimation plus basse
        # Mais notre algorithme applique le facteur après l'estimation de base
        assert estimated <= english_estimate
        assert estimated >= 1  # Minimum

    def test_estimate_tokens_code(self):
        """Test l'estimation pour le code."""
        text = "def function_name(param): return param * 2"  # 39 caractères
        # Base: 39 // 4 = 9.75 → 10 tokens
        # Facteur code: 0.7 → 7 tokens
        assert TokenEstimator.estimate_tokens(text, "code") == 7

    def test_estimate_tokens_empty(self):
        """Test l'estimation pour un texte vide."""
        assert TokenEstimator.estimate_tokens("") == 0

    def test_estimate_tokens_short_text(self):
        """Test l'estimation pour un texte très court."""
        text = "Hi"  # 2 caractères
        # Minimum de 3 tokens pour les textes courts
        assert TokenEstimator.estimate_tokens(text) == 3


class TestMessagesEstimation:
    """Tests pour l'estimation des messages."""

    def test_estimate_messages_tokens_simple(self):
        """Test l'estimation pour des messages simples."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        # Message 1: "Hello" (5 chars) → 5//4=1.25→2 tokens + 4 overhead = 6
        # Message 2: "Hi there" (8 chars) → 8//4=2 tokens + 4 overhead = 6
        # Total: 12 tokens
        estimated = TokenEstimator.estimate_messages_tokens(messages)
        assert estimated >= 10  # Estimation raisonnable

    def test_estimate_messages_tokens_with_system(self):
        """Test l'estimation avec un message système."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is 2+2?"},
        ]
        estimated = TokenEstimator.estimate_messages_tokens(messages)
        assert estimated >= 15  # Doit être plus élevé à cause du rôle système

    def test_estimate_messages_tokens_multimodal(self):
        """Test l'estimation pour des messages multi-modaux."""
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe this image"},
                    {
                        "type": "image_url",
                        "image_url": {"url": "data:image/jpeg;base64,..."},
                    },
                ],
            }
        ]
        # Ne doit compter que la partie texte
        estimated = TokenEstimator.estimate_messages_tokens(messages)
        assert estimated >= 5


class TestPayloadEstimation:
    """Tests pour l'estimation des payloads complets."""

    def test_estimate_input_tokens_basic(self):
        """Test l'estimation d'entrée basique."""
        payload = {"messages": [{"role": "user", "content": "Hello world"}]}
        estimated = TokenEstimator.estimate_input_tokens(payload)
        assert estimated >= 10  # Messages + overhead de requête

    def test_estimate_input_tokens_with_params(self):
        """Test l'estimation avec paramètres."""
        payload = {
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 100,
            "temperature": 0.7,
            "top_p": 0.9,
        }
        estimated = TokenEstimator.estimate_input_tokens(payload)
        assert estimated >= 15  # Plus élevé à cause des paramètres

    def test_estimate_output_tokens_with_max_tokens(self):
        """Test l'estimation de sortie avec max_tokens spécifié."""
        payload = {"max_tokens": 500}
        assert TokenEstimator.estimate_output_tokens(payload) == 500

    def test_estimate_output_tokens_default(self):
        """Test l'estimation de sortie par défaut."""
        payload = {
            "messages": [
                {"role": "user", "content": "Hello world" * 10}  # ~110 caractères
            ]
        }
        estimated = TokenEstimator.estimate_output_tokens(payload)
        # Doit être proportionnel aux tokens d'entrée, avec un maximum
        assert estimated > 0
        assert estimated <= 4096  # Maximum raisonnable


class TestCompatibilityFunctions:
    """Tests pour les fonctions de compatibilité."""

    def test_estimate_input_tokens_compatibility(self):
        """Test la fonction de compatibilité estimate_input_tokens."""
        payload = {"messages": [{"role": "user", "content": "Test message"}]}
        estimated = estimate_input_tokens(payload)
        assert estimated > 0
        # Doit être différent de l'ancienne estimation naïve
        old_estimate = len("Test message") // 4
        assert estimated != old_estimate  # Nouvelle estimation améliorée

    def test_estimate_output_tokens_compatibility(self):
        """Test la fonction de compatibilité estimate_output_tokens."""
        payload = {"max_tokens": 200}
        assert estimate_output_tokens(payload) == 200

        payload_no_max = {}
        estimated = estimate_output_tokens(payload_no_max)
        assert estimated <= 4096  # Maximum raisonnable


class TestAccuracyComparison:
    """Tests comparant la nouvelle estimation avec l'ancienne."""

    def test_english_text_comparison(self):
        """Compare l'estimation pour un texte anglais."""
        text = "This is a relatively long English text that should demonstrate the difference between the old and new estimation algorithms."

        # Ancienne estimation
        old_estimate = len(text) // 4

        # Nouvelle estimation
        new_estimate = TokenEstimator.estimate_tokens(text)

        # La nouvelle estimation devrait être dans une plage raisonnable
        assert new_estimate > 0
        assert new_estimate <= 100
        # Les deux estimations peuvent être similaires pour l'anglais simple
        # L'important est que la nouvelle soit plus précise pour d'autres cas

    def test_code_comparison(self):
        """Compare l'estimation pour du code."""
        code = """
def calculate_sum(numbers):
    total = 0
    for num in numbers:
        total += num
    return total
"""

        # Ancienne estimation
        old_estimate = len(code) // 4

        # Nouvelle estimation (avec détection automatique du code)
        new_estimate = TokenEstimator.estimate_tokens(code)

        # La nouvelle estimation devrait être plus basse pour le code
        assert new_estimate < old_estimate

    def test_french_text_comparison(self):
        """Compare l'estimation pour un texte français."""
        text = "Ceci est un texte français avec des caractères accentués qui devrait produire une estimation différente de l'ancien algorithme."

        # Ancienne estimation
        old_estimate = len(text) // 4

        # Nouvelle estimation
        new_estimate = TokenEstimator.estimate_tokens(text)

        # La nouvelle estimation devrait être plus élevée pour le français
        assert new_estimate > old_estimate
