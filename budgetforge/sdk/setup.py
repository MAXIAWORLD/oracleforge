from setuptools import setup

setup(
    name="budgetforge",
    version="0.1.0",
    description="BudgetForge SDK — LLM proxy with budget enforcement",
    py_modules=["budgetforge_sdk"],
    install_requires=[
        "httpx>=0.24.0",
    ],
    python_requires=">=3.8",
)
