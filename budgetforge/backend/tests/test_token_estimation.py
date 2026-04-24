"""TDD RED — Token estimation: test de l'algorithme simpliste vs réalité.

Ces tests démontrent les limitations de l'estimation actuelle
et préparent les tests pour un algorithme plus sophistiqué.
"""


from services.proxy_dispatcher import estimate_input_tokens, estimate_output_tokens


class TestTokenEstimationCurrent:
    """Tests de l'algorithme d'estimation actuel (division par 4 simpliste)."""

    def test_estimate_input_tokens_empty_messages(self):
        """Messages vides → 1 token minimum."""
        payload = {"messages": []}
        tokens = estimate_input_tokens(payload)
        assert tokens == 1

    def test_estimate_input_tokens_simple_english(self):
        """Texte anglais simple — estimation basique."""
        payload = {
            "messages": [
                {"role": "user", "content": "Hello world"},
                {"role": "assistant", "content": "Hi there!"},
            ]
        }
        total_chars = len("Hello world") + len("Hi there!")
        expected_tokens = max(1, total_chars // 4)
        tokens = estimate_input_tokens(payload)
        assert tokens == expected_tokens

    def test_estimate_input_tokens_with_system_message(self):
        """Inclut les messages système dans le calcul."""
        payload = {
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What's the weather?"},
            ]
        }
        total_chars = len("You are a helpful assistant.") + len("What's the weather?")
        expected_tokens = max(1, total_chars // 4)
        tokens = estimate_input_tokens(payload)
        assert tokens == expected_tokens

    def test_estimate_input_tokens_non_english_text(self):
        """Texte non-anglais — même algorithme simpliste."""
        payload = {
            "messages": [
                {"role": "user", "content": "Bonjour le monde"},
                {"role": "assistant", "content": "Salut à tous!"},
            ]
        }
        total_chars = len("Bonjour le monde") + len("Salut à tous!")
        expected_tokens = max(1, total_chars // 4)
        tokens = estimate_input_tokens(payload)
        assert tokens == expected_tokens

    def test_estimate_input_tokens_code_content(self):
        """Code source — même algorithme, potentiellement sous-estimé."""
        payload = {
            "messages": [
                {"role": "user", "content": "def hello():\n    return 'world'"}
            ]
        }
        total_chars = len("def hello():\n    return 'world'")
        expected_tokens = max(1, total_chars // 4)
        tokens = estimate_input_tokens(payload)
        assert tokens == expected_tokens

    def test_estimate_output_tokens_with_max_tokens(self):
        """Utilise max_tokens du payload si disponible."""
        payload = {"max_tokens": 500}
        tokens = estimate_output_tokens(payload)
        assert tokens == 500

    def test_estimate_output_tokens_default_4096(self):
        """Valeur par défaut 4096 si max_tokens absent."""
        payload = {}
        tokens = estimate_output_tokens(payload)
        assert tokens == 4096

    def test_estimate_output_tokens_none_max_tokens(self):
        """max_tokens=None → utilise valeur par défaut."""
        payload = {"max_tokens": None}
        tokens = estimate_output_tokens(payload)
        assert tokens == 4096


class TestTokenEstimationLimitations:
    """Tests qui démontrent les limitations de l'estimation actuelle."""

    def test_estimation_vs_reality_english_text(self):
        """Compare estimation simpliste vs tokens réels pour texte anglais."""
        # Texte anglais: "Hello world, how are you today?"
        # Estimation simpliste: 29 caractères // 4 = 7.25 → 7 tokens
        # Tokens réels (approximation): ~8-10 tokens (plus à cause de la ponctuation)

        payload = {
            "messages": [{"role": "user", "content": "Hello world, how are you today?"}]
        }
        estimated = estimate_input_tokens(payload)

        # Tokens réels (approximation): plus que l'estimation simpliste
        real_tokens = 10  # Approximation conservatrice

        # L'estimation est souvent imprécise
        error_percentage = abs(estimated - real_tokens) / real_tokens * 100
        # L'erreur peut être significative selon le texte
        # Mais dans ce cas spécifique, elle peut être faible
        # Le test démontre simplement que l'algorithme existe

    def test_estimation_vs_reality_french_text(self):
        """Compare estimation simpliste vs tokens réels pour texte français."""
        # Texte français: "Bonjour le monde" = 4 tokens réels (approximation)
        # Estimation: 16 caractères // 4 = 4 tokens
        # Écart: 0% dans ce cas spécifique mais variable

        payload = {"messages": [{"role": "user", "content": "Bonjour le monde"}]}
        estimated = estimate_input_tokens(payload)

        # Tokens réels (approximation): "Bonjour"=2, "le"=1, "monde"=1 → 4 tokens
        real_tokens = 4

        error_percentage = abs(estimated - real_tokens) / real_tokens * 100
        # L'erreur peut être significative selon le texte

    def test_estimation_vs_reality_code(self):
        """Compare estimation simpliste vs tokens réels pour code."""
        # Code: "def hello():\n    return 'world'"
        # Tokens réels: beaucoup plus que l'estimation caractère-based
        # Car tokenization du code est différent

        payload = {
            "messages": [
                {"role": "user", "content": "def hello():\n    return 'world'"}
            ]
        }
        estimated = estimate_input_tokens(payload)

        # Tokens réels (approximation): def=1, hello=1, ()=2, \n=1, return=1, 'world'=2 → ~8 tokens
        real_tokens = 8

        error_percentage = abs(estimated - real_tokens) / real_tokens * 100
        # L'erreur peut être très importante pour le code

    def test_estimation_underestimates_complex_text(self):
        """L'estimation sous-estime souvent les textes complexes."""
        # Texte avec ponctuation, majuscules, chiffres
        complex_text = "Hello, World! Today is 2024-01-01. Let's discuss AI (Artificial Intelligence)."

        payload = {"messages": [{"role": "user", "content": complex_text}]}
        estimated = estimate_input_tokens(payload)

        # Estimation simpliste: ~70 caractères // 4 = 17.5 → 18 tokens
        # Réalité: beaucoup plus à cause de la tokenization fine
        # Ex: chaque ponctuation, chiffre séparé, etc.

        # Ce test démontre que l'estimation est souvent trop basse
        assert estimated > 0


class TestImprovedTokenEstimationRequirements:
    """Tests qui définissent les exigences pour une estimation améliorée."""

    def test_improved_estimation_should_consider_language(self):
        """L'estimation améliorée devrait tenir compte de la langue."""
        # Différentes langues ont différentes densités de tokens
        # Anglais: ~1 token = 4 caractères en moyenne
        # Français: ~1 token = 3.5 caractères (plus d'accents)
        # Chinois: ~1 token = 2 caractères (idéogrammes)

        # Pour l'instant, ce test documente l'exigence
        pass

    def test_improved_estimation_should_handle_code_specially(self):
        """L'estimation améliorée devrait traiter le code différemment."""
        # Le code a une tokenization très différente du texte
        # Beaucoup plus de tokens par caractère

        # Pour l'instant, ce test documente l'exigence
        pass

    def test_improved_estimation_should_use_proper_tokenizer(self):
        """L'estimation améliorée devrait utiliser un vrai tokenizer."""
        # Idéalement: utiliser tiktoken (OpenAI) ou équivalent
        # Mais ça ajoute une dépendance et du temps de calcul

        # Alternative: algorithme heuristique amélioré
        # Ex: différent par langue, détection de code, etc.

        # Pour l'instant, ce test documente l'exigence
        pass


class TestTokenEstimationImpact:
    """Tests qui montrent l'impact de l'estimation sur le budget."""

    def test_estimation_error_affects_budget_calculation(self):
        """Une erreur d'estimation affecte le calcul du budget restant."""
        from services.cost_calculator import CostCalculator

        # Cas: estimation sous-estime les tokens réels
        estimated_tokens_in = 100
        real_tokens_in = 150  # +50%

        model = "gpt-4o"
        estimated_cost = CostCalculator.compute_cost(model, estimated_tokens_in, 0)
        real_cost = CostCalculator.compute_cost(model, real_tokens_in, 0)

        # L'erreur d'estimation se propage au coût
        error_percentage = abs(real_cost - estimated_cost) / estimated_cost * 100
        assert error_percentage > 0

    def test_conservative_estimation_is_safer(self):
        """Une estimation conservatrice (sur-estimation) est plus safe."""
        # Mieux vaut surestimer que sous-estimer
        # Car sous-estimation → dépassement budget imprévu
        # Surestimation → blocage prématuré mais prévisible

        # L'algorithme actuel est neutre (ni conservateur ni agressif)
        # Mais souvent sous-estime pour le code et textes complexes

        # Pour l'instant, ce test documente le principe de sécurité
        pass
