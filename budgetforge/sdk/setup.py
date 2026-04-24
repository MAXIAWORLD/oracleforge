import os
from setuptools import setup

setup(
    name="budgetforge",
    version="0.1.1",
    description="BudgetForge SDK — LLM proxy with budget enforcement",
    long_description=open("README.md").read() if os.path.exists("README.md") else "",
    long_description_content_type="text/markdown",
    author="MAXIA",
    author_email="majorel.alexis@gmail.com",
    url="https://github.com/maxialab/budgetforge",
    py_modules=["budgetforge_sdk"],
    install_requires=[
        "httpx>=0.24.0",
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
