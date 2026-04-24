#!/usr/bin/env python3
"""
AWS Bedrock Usage Examples for BudgetForge

This file provides practical examples of using AWS Bedrock through BudgetForge's proxy.
"""

import os
import requests
import json

# Configuration
BUDGETFORGE_BASE_URL = "http://localhost:8011"
PROJECT_API_KEY = os.getenv("BUDGETFORGE_API_KEY", "bf-your-project-api-key")


def basic_chat_completion():
    """Basic chat completion using Claude 3 Sonnet."""

    payload = {
        "model": "anthropic.claude-3-sonnet",
        "messages": [
            {
                "role": "user",
                "content": "Explain the concept of machine learning in simple terms.",
            }
        ],
        "temperature": 0.7,
        "max_tokens": 500,
    }

    response = requests.post(
        f"{BUDGETFORGE_BASE_URL}/proxy/aws-bedrock/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {PROJECT_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
    )

    if response.status_code == 200:
        result = response.json()
        print("✅ Success!")
        print(f"Response: {result['choices'][0]['message']['content']}")
        print(f"Usage: {result['usage']}")
    else:
        print(f"❌ Error: {response.status_code} - {response.text}")


def streaming_chat():
    """Streaming chat completion for real-time responses."""

    payload = {
        "model": "anthropic.claude-3-haiku",
        "messages": [
            {
                "role": "user",
                "content": "Write a creative story about a robot exploring Mars.",
            }
        ],
        "stream": True,
        "temperature": 0.8,
    }

    response = requests.post(
        f"{BUDGETFORGE_BASE_URL}/proxy/aws-bedrock/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {PROJECT_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        stream=True,
    )

    print("🚀 Streaming response:")
    for line in response.iter_lines():
        if line:
            line_text = line.decode("utf-8")
            if line_text.startswith("data: "):
                data = line_text[6:]  # Remove 'data: ' prefix
                if data != "[DONE]":
                    try:
                        chunk = json.loads(data)
                        if "choices" in chunk and chunk["choices"]:
                            delta = chunk["choices"][0].get("delta", {})
                            if "content" in delta:
                                print(delta["content"], end="", flush=True)
                    except json.JSONDecodeError:
                        pass
    print("\n✅ Streaming complete")


def code_generation_with_llama():
    """Code generation using LLaMA models."""

    payload = {
        "model": "meta.llama3-70b-instruct",
        "messages": [
            {
                "role": "user",
                "content": "Write a Python function to calculate fibonacci numbers with memoization.",
            }
        ],
        "temperature": 0.2,  # Lower temperature for code generation
        "max_tokens": 1000,
    }

    response = requests.post(
        f"{BUDGETFORGE_BASE_URL}/proxy/aws-bedrock/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {PROJECT_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
    )

    if response.status_code == 200:
        result = response.json()
        print("✅ Code generation successful!")
        print("Generated code:")
        print("-" * 50)
        print(result["choices"][0]["message"]["content"])
        print("-" * 50)
    else:
        print(f"❌ Error: {response.status_code} - {response.text}")


def multi_turn_conversation():
    """Multi-turn conversation with context retention."""

    conversation = [
        {"role": "user", "content": "What are the main benefits of renewable energy?"},
        {
            "role": "assistant",
            "content": "Renewable energy offers several key benefits...",
        },
        {
            "role": "user",
            "content": "Can you compare solar and wind energy specifically?",
        },
    ]

    payload = {
        "model": "anthropic.claude-3-sonnet",
        "messages": conversation,
        "temperature": 0.5,
    }

    response = requests.post(
        f"{BUDGETFORGE_BASE_URL}/proxy/aws-bedrock/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {PROJECT_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
    )

    if response.status_code == 200:
        result = response.json()
        print("✅ Multi-turn conversation successful!")
        print(f"Response: {result['choices'][0]['message']['content']}")
    else:
        print(f"❌ Error: {response.status_code} - {response.text}")


def cost_effective_haiku_usage():
    """Example of cost-effective usage with Claude Haiku."""

    payload = {
        "model": "anthropic.claude-3-haiku",
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful assistant that provides concise answers.",
            },
            {
                "role": "user",
                "content": "Summarize the key points about climate change in 3 bullet points.",
            },
        ],
        "temperature": 0.1,  # Low temperature for consistent, concise responses
        "max_tokens": 300,  # Limit response length
    }

    response = requests.post(
        f"{BUDGETFORGE_BASE_URL}/proxy/aws-bedrock/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {PROJECT_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
    )

    if response.status_code == 200:
        result = response.json()
        print("✅ Cost-effective usage successful!")
        print(f"Response: {result['choices'][0]['message']['content']}")
        print(f"Estimated cost: ${result['usage']['total_tokens'] * 0.0000008:.6f}")
    else:
        print(f"❌ Error: {response.status_code} - {response.text}")


def error_handling_example():
    """Example of proper error handling."""

    try:
        # Intentional error - invalid model name
        payload = {
            "model": "invalid-model-name",
            "messages": [{"role": "user", "content": "Hello"}],
        }

        response = requests.post(
            f"{BUDGETFORGE_BASE_URL}/proxy/aws-bedrock/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {PROJECT_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )

        if response.status_code == 200:
            print("✅ Request successful")
        else:
            print(f"❌ Error {response.status_code}: {response.text}")

    except requests.exceptions.Timeout:
        print("❌ Request timed out")
    except requests.exceptions.ConnectionError:
        print("❌ Connection error - check BudgetForge server")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")


def batch_processing_example():
    """Example of processing multiple requests efficiently."""

    questions = [
        "What is the capital of France?",
        "Explain the concept of blockchain.",
        "What are the health benefits of exercise?",
    ]

    print("🔁 Processing batch of questions...")

    for i, question in enumerate(questions, 1):
        payload = {
            "model": "anthropic.claude-3-haiku",
            "messages": [{"role": "user", "content": question}],
            "max_tokens": 150,
        }

        response = requests.post(
            f"{BUDGETFORGE_BASE_URL}/proxy/aws-bedrock/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {PROJECT_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
        )

        if response.status_code == 200:
            result = response.json()
            print(f"{i}. {question}")
            print(f"   Answer: {result['choices'][0]['message']['content'][:100]}...")
        else:
            print(f"{i}. ❌ Failed: {response.status_code}")


def main():
    """Run all examples."""

    print("=" * 60)
    print("AWS Bedrock BudgetForge Examples")
    print("=" * 60)

    examples = [
        ("Basic Chat Completion", basic_chat_completion),
        ("Streaming Chat", streaming_chat),
        ("Code Generation with LLaMA", code_generation_with_llama),
        ("Multi-turn Conversation", multi_turn_conversation),
        ("Cost-effective Haiku Usage", cost_effective_haiku_usage),
        ("Error Handling", error_handling_example),
        ("Batch Processing", batch_processing_example),
    ]

    for name, function in examples:
        print(f"\n🎯 {name}")
        print("-" * 40)
        try:
            function()
        except Exception as e:
            print(f"❌ Example failed: {e}")
        print("-" * 40)


if __name__ == "__main__":
    main()
