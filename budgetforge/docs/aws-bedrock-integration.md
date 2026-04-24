# AWS Bedrock Integration Guide

BudgetForge provides native support for AWS Bedrock, allowing you to use Amazon's managed foundation models through BudgetForge's budget management and cost tracking features.

## Overview

AWS Bedrock integration enables access to:
- **Anthropic Claude models** (Claude-3 Opus, Sonnet, Haiku)
- **Meta LLaMA models** (LLaMA 2 & 3)
- **Amazon Titan models** (when available)

All through BudgetForge's unified proxy interface with full cost tracking and budget enforcement.

## Configuration

### 1. AWS Credentials Setup

Add your AWS credentials to your `.env` file:

```bash
# AWS Bedrock Configuration
AWS_BEDROCK_ACCESS_KEY=your-aws-access-key-id
AWS_BEDROCK_SECRET_KEY=your-aws-secret-access-key
AWS_BEDROCK_REGION=us-east-1  # or your preferred region
```

### 2. IAM Permissions

Ensure your AWS IAM user/role has the following permissions:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "bedrock:InvokeModel",
                "bedrock:InvokeModelWithResponseStream"
            ],
            "Resource": "*"
        }
    ]
}
```

## Available Models

### Anthropic Claude Models
- `anthropic.claude-v2` - Claude 2.1
- `anthropic.claude-v2:1` - Claude 2.1 (latest)
- `anthropic.claude-3-haiku` - Fast, cost-effective
- `anthropic.claude-3-sonnet` - Balanced performance
- `anthropic.claude-3-opus` - Most capable

### Meta LLaMA Models
- `meta.llama2-13b-chat` - LLaMA 2 13B Chat
- `meta.llama2-70b-chat` - LLaMA 2 70B Chat
- `meta.llama3-8b-instruct` - LLaMA 3 8B Instruct
- `meta.llama3-70b-instruct` - LLaMA 3 70B Instruct

## Usage Examples

### Basic Chat Completion

```python
import requests

response = requests.post(
    "http://localhost:8011/proxy/aws-bedrock/v1/chat/completions",
    headers={
        "Authorization": "Bearer bf-your-project-api-key",
        "Content-Type": "application/json"
    },
    json={
        "model": "anthropic.claude-3-sonnet",
        "messages": [
            {"role": "user", "content": "Explain quantum computing in simple terms"}
        ],
        "temperature": 0.7,
        "max_tokens": 1000
    }
)

print(response.json())
```

### Streaming Response

```python
import requests

response = requests.post(
    "http://localhost:8011/proxy/aws-bedrock/v1/chat/completions",
    headers={
        "Authorization": "Bearer bf-your-project-api-key",
        "Content-Type": "application/json"
    },
    json={
        "model": "anthropic.claude-3-haiku",
        "messages": [
            {"role": "user", "content": "Write a short poem about AI"}
        ],
        "stream": True
    },
    stream=True
)

for line in response.iter_lines():
    if line:
        print(line.decode('utf-8'))
```

### Using LLaMA Models

```python
import requests

response = requests.post(
    "http://localhost:8011/proxy/aws-bedrock/v1/chat/completions",
    headers={
        "Authorization": "Bearer bf-your-project-api-key",
        "Content-Type": "application/json"
    },
    json={
        "model": "meta.llama3-70b-instruct",
        "messages": [
            {"role": "user", "content": "Explain the benefits of open source AI models"}
        ],
        "temperature": 0.3
    }
)

print(response.json())
```

## Cost Tracking

BudgetForge automatically tracks costs for AWS Bedrock usage:

### Current Pricing (per 1M tokens)

| Model | Input | Output |
|-------|-------|--------|
| Claude 3 Opus | $15.00 | $75.00 |
| Claude 3 Sonnet | $3.00 | $15.00 |
| Claude 3 Haiku | $0.80 | $4.00 |
| Claude 2.1 | $8.00 | $24.00 |
| LLaMA 2 70B | $2.05 | $2.05 |
| LLaMA 2 13B | $0.75 | $0.75 |
| LLaMA 3 70B | $2.65 | $2.65 |
| LLaMA 3 8B | $0.60 | $0.60 |

### Budget Enforcement

Set project budgets to control AWS Bedrock spending:

```python
# Example: Set $100 monthly budget with downgrade chain
project_settings = {
    "budget_usd": 100.0,
    "reset_period": "monthly",
    "action": "downgrade",
    "downgrade_chain": [
        "anthropic.claude-3-opus",
        "anthropic.claude-3-sonnet", 
        "anthropic.claude-3-haiku",
        "meta.llama3-70b-instruct"
    ]
}
```

## Error Handling

### Common Errors

```python
try:
    response = requests.post(
        "http://localhost:8011/proxy/aws-bedrock/v1/chat/completions",
        headers={"Authorization": "Bearer bf-your-key"},
        json={"model": "anthropic.claude-3-sonnet", "messages": [...]}
    )
    
    if response.status_code == 400:
        print("Invalid request or missing AWS credentials")
    elif response.status_code == 502:
        print("AWS Bedrock service unavailable")
    elif response.status_code == 429:
        print("Budget exceeded or rate limited")
        
except requests.exceptions.RequestException as e:
    print(f"Network error: {e}")
```

### Retry Logic

```python
import time
import requests

def call_bedrock_with_retry(payload, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = requests.post(
                "http://localhost:8011/proxy/aws-bedrock/v1/chat/completions",
                headers={"Authorization": "Bearer bf-your-key"},
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            
            # Exponential backoff for retries
            time.sleep(2 ** attempt)
            
        except requests.exceptions.Timeout:
            print(f"Timeout on attempt {attempt + 1}")
            
    raise Exception("All retries failed")
```

## Best Practices

### 1. Model Selection
- Use Claude Haiku for high-volume, cost-sensitive tasks
- Use Claude Sonnet for balanced performance
- Use Claude Opus for complex reasoning tasks
- Use LLaMA models for open-source requirements

### 2. Cost Optimization
- Set appropriate temperature values (0.1-0.3 for deterministic tasks)
- Use max_tokens to control response length
- Implement caching for repetitive queries
- Monitor usage through BudgetForge dashboard

### 3. Performance
- AWS Bedrock provides consistent latency and throughput
- Consider regional placement for latency-sensitive applications
- Use streaming for better user experience

## Monitoring

### BudgetForge Dashboard
Monitor your AWS Bedrock usage through the BudgetForge dashboard:
- Real-time cost tracking
- Usage analytics by model
- Budget alerts and notifications

### AWS CloudWatch
For detailed AWS-side monitoring:
- Enable CloudWatch logging for Bedrock
- Monitor API call metrics
- Set up billing alerts in AWS

## Troubleshooting

### Common Issues

1. **"AWS Bedrock non configuré"**
   - Check AWS credentials in `.env`
   - Verify IAM permissions
   - Confirm AWS region supports Bedrock

2. **"Model not found"**
   - Check model name spelling
   - Verify model availability in your AWS region
   - Ensure model access is granted

3. **High latency**
   - Check AWS region proximity
   - Monitor network connectivity
   - Consider using closer regions

### Support

For AWS Bedrock-specific issues:
- AWS Support: https://aws.amazon.com/contact-us/
- AWS Bedrock Documentation: https://docs.aws.amazon.com/bedrock/

For BudgetForge integration issues:
- BudgetForge Documentation: https://budgetforge.io/docs
- GitHub Issues: https://github.com/budgetforge/budgetforge/issues

## Migration from Direct AWS Calls

If you're migrating from direct AWS Bedrock API calls:

### Before (Direct AWS)
```python
import boto3

client = boto3.client('bedrock-runtime', region_name='us-east-1')

response = client.invoke_model(
    modelId='anthropic.claude-v2',
    body=json.dumps({
        "prompt": "\n\nHuman: Hello\n\nAssistant:",
        "max_tokens_to_sample": 300
    })
)
```

### After (BudgetForge)
```python
import requests

response = requests.post(
    "http://localhost:8011/proxy/aws-bedrock/v1/chat/completions",
    headers={"Authorization": "Bearer bf-your-key"},
    json={
        "model": "anthropic.claude-v2",
        "messages": [{"role": "user", "content": "Hello"}]
    }
)
```

The BudgetForge approach provides automatic cost tracking, budget enforcement, and unified error handling across all LLM providers.