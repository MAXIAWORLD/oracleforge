"""Setup configuration for Langchain BudgetForge SDK."""

from setuptools import setup, find_packages

setup(
    name="langchain-budgetforge",
    version="0.1.0",
    description="Langchain integration for BudgetForge API with budget enforcement",
    packages=find_packages(),
    install_requires=[
        "langchain-core>=0.1.0",
        "httpx>=0.24.0",
        "pydantic>=2.0.0",
    ],
    python_requires=">=3.8",
)
