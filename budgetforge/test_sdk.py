"""Test simple du SDK Langchain BudgetForge."""

import sys
import os

# Ajoute le chemin du SDK au PYTHONPATH
sdk_path = os.path.join(os.path.dirname(__file__), "langchain_budgetforge")
sys.path.insert(0, sdk_path)

try:
    from langchain_budgetforge import BudgetForgeLLM, BudgetForgeChat

    print("SUCCESS: SDK importé avec succès")

    # Test d'initialisation
    llm = BudgetForgeLLM(api_key="test-key", model="gpt-4", provider="openai")
    print("SUCCESS: BudgetForgeLLM initialisé")

    chat = BudgetForgeChat(
        api_key="test-key", model="claude-3-sonnet", provider="anthropic"
    )
    print("SUCCESS: BudgetForgeChat initialisé")

    print("\nSUCCESS: SDK Langchain BudgetForge fonctionne correctement!")

except ImportError as e:
    print(f"ERROR: Erreur d'import: {e}")
    print(f"Chemin SDK: {sdk_path}")
    print(
        f"Contenu du répertoire: {os.listdir(sdk_path) if os.path.exists(sdk_path) else 'Répertoire inexistant'}"
    )
except Exception as e:
    print(f"ERROR: Erreur: {e}")
