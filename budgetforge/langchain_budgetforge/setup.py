"""Setup configuration for Langchain BudgetForge SDK."""

import os
from setuptools import setup, find_packages

setup(
    name="langchain-budgetforge",
    version="0.1.1",
    description="Langchain integration for BudgetForge API with budget enforcement",
    long_description=open("README.md").read() if os.path.exists("README.md") else "",
    long_description_content_type="text/markdown",
    author="MAXIA",
    author_email="majorel.alexis@gmail.com",
    url="https://github.com/maxialab/budgetforge",
    packages=find_packages(),
    install_requires=[
        "langchain-core>=0.1.0",
        "httpx>=0.24.0",
        "pydantic>=2.0.0",
    ],
    python_requires=">=3.8",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)
