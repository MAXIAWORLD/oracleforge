# BudgetForge API Reference

## Overview
BudgetForge is a proxy layer that adds budget enforcement and monitoring to LLM API calls.

**Base URL**: `https://llmbudget.maxiaworld.app`

## Authentication

### API Key Authentication
Use for project-specific endpoints:
```http
Authorization: Bearer <PROJECT_API_KEY>
```

### JWT Authentication  
Use for user management endpoints:
```http
Authorization: Bearer <JWT_TOKEN>
```

## Rate Limits

| Endpoint | Limit |
|----------|-------|
| `/api/public/test` | 60/minute |
| Proxy endpoints | 30/minute, 1000/hour |
| Project management | 60/minute |
| Admin endpoints | 5/minute |

## Core Endpoints

### Projects
- `GET /api/projects` - List all projects
- `POST /api/projects` - Create new project
- `GET /api/projects/{id}` - Get project details
- `PUT /api/projects/{id}` - Update project
- `DELETE /api/projects/{id}` - Delete project

### Proxy Endpoints
All proxy endpoints require `Authorization: Bearer <API_KEY>`

#### OpenAI Compatible
```http
POST /proxy/openai/v1/chat/completions
Content-Type: application/json
Authorization: Bearer <API_KEY>

{
  "model": "gpt-4",
  "messages": [...]
}
```

#### Anthropic
```http
POST /proxy/anthropic/v1/messages
Content-Type: application/json
Authorization: Bearer <API_KEY>

{
  "model": "claude-3-sonnet-20240229",
  "messages": [...]
}
```

#### OpenRouter
```http
POST /proxy/openrouter/v1/chat/completions
Content-Type: application/json
Authorization: Bearer <API_KEY>

{
  "model": "openai/gpt-4",
  "messages": [...]
}
```

### Authentication
- `POST /auth/token` - Get JWT tokens (API key → JWT)
- `POST /auth/refresh` - Refresh JWT tokens
- `GET /auth/verify` - Verify token validity

### Usage & Analytics
- `GET /api/usage/{project_id}` - Get usage statistics
- `GET /api/history` - Get call history
- `GET /api/export` - Export data (CSV)

## Error Handling

### Common Status Codes
- `200` - Success
- `400` - Bad request (invalid parameters)
- `401` - Unauthorized (invalid/missing auth)
- `402` - Payment required (plan upgrade needed)
- `429` - Rate limit exceeded
- `500` - Internal server error

### Budget Exceeded
When a project exceeds its budget:
```json
{
  "error": "Budget exceeded",
  "project_id": 123,
  "budget_usd": 100.0,
  "used_usd": 105.2,
  "action": "block"
}
```

## Models Endpoint

Get available models with pricing:
```http
GET /api/models
Authorization: Bearer <API_KEY>
```

Response:
```json
[
  {
    "id": "gpt-4",
    "name": "GPT-4",
    "provider": "openai",
    "context_window": 8192,
    "input_price_per_token": 0.00003,
    "output_price_per_token": 0.00006
  }
]
```

## Webhooks

Configure webhooks for budget alerts:
```http
PUT /api/projects/{id}
Authorization: Bearer <API_KEY>

{
  "webhook_url": "https://your-app.com/webhooks/budget",
  "webhook_events": ["budget_exceeded", "budget_warning"]
}
```

## Testing

Public endpoint for testing connectivity and rate limits:
```http
GET /api/public/test
```

## SDKs

### Python
```python
import requests

api_key = "your_project_api_key"
base_url = "https://llmbudget.maxiaworld.app"

# Make a proxy call
response = requests.post(
    f"{base_url}/proxy/openai/v1/chat/completions",
    headers={"Authorization": f"Bearer {api_key}"},
    json={
        "model": "gpt-4",
        "messages": [{"role": "user", "content": "Hello"}]
    }
)
```

### JavaScript
```javascript
const apiKey = 'your_project_api_key';
const baseUrl = 'https://llmbudget.maxiaworld.app';

// Make a proxy call
const response = await fetch(`${baseUrl}/proxy/openai/v1/chat/completions`, {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${apiKey}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    model: 'gpt-4',
    messages: [{ role: 'user', content: 'Hello' }]
  })
});
```

## Support

- **Email**: ceo@maxiaworld.app
- **Documentation**: https://llmbudget.maxiaworld.app/docs
- **Status**: https://status.maxiaworld.app