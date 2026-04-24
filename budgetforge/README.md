# BudgetForge

**LLM Budget Guard** — Proxy layer with hard limits per project/user/agent

[![Production Ready](https://img.shields.io/badge/production-ready-brightgreen)](https://llmbudget.maxiaworld.app)
[![Tests Passing](https://img.shields.io/badge/tests-742%2F742-green)](./backend/tests)
[![Security](https://img.shields.io/badge/security-audited-blue)](./backend/docs/security-audit.md)

## 🚀 Quick Start

### 1. Create Project
```bash
curl -X POST https://llmbudget.maxiaworld.app/api/projects \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-llm-app",
    "budget_usd": 100.0
  }'
```

### 2. Use API Key
```bash
# Response contains your API key
{
  "id": 123,
  "name": "my-llm-app", 
  "api_key": "bf_xxxxxxxxxxxx",
  "budget_usd": 100.0
}
```

### 3. Make LLM Calls
```bash
curl -X POST https://llmbudget.maxiaworld.app/proxy/openai/v1/chat/completions \
  -H "Authorization: Bearer bf_xxxxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

## ✨ Features

- **🔒 Budget Enforcement** - Hard limits per project
- **🔄 Multi-Provider** - OpenAI, Anthropic, Google, OpenRouter, etc.
- **📊 Real-time Monitoring** - Usage analytics and dashboards
- **🚨 Smart Alerts** - Email/Slack notifications
- **🔐 JWT Authentication** - Secure token-based auth
- **⚡ Rate Limiting** - Prevent abuse and overuse
- **💸 Cost Control** - Dynamic pricing and downgrade chains

## 📚 Documentation

- [**API Reference**](./docs/api-reference.md) - Complete endpoint documentation
- [**OpenAPI Spec**](./docs/openapi.json) - Machine-readable API specification
- [**Deployment Guide**](./docs/deployment-guide.md) - Production setup instructions
- [**Security Audit**](./backend/docs/security-audit.md) - Security best practices

## 🏗️ Architecture

```
Client App → BudgetForge Proxy → LLM Providers (OpenAI, Anthropic, etc.)
                ↓
        Budget Enforcement & Monitoring
                ↓
          Analytics & Alerts
```

## 🔧 Installation

### Local Development
```bash
git clone https://github.com/maxia-lab/budgetforge
cd budgetforge/backend

# Setup virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Run tests
python -m pytest tests/ -v

# Start server
uvicorn main:app --reload
```

### Production Deployment
See [Deployment Guide](./docs/deployment-guide.md) for detailed instructions.

## 🎯 Use Cases

### Startups & SMEs
- Control LLM API costs during development
- Prevent budget overruns in production
- Monitor usage across team members

### Enterprise
- Multi-team project isolation
- Compliance and audit trails
- Centralized cost management

### Agencies
- Client project budgeting
- Usage reporting and billing
- Multi-model flexibility

## 🔌 Supported Providers

| Provider | Status | Models |
|----------|--------|--------|
| OpenAI | ✅ | GPT-4, GPT-3.5, etc. |
| Anthropic | ✅ | Claude-3, Claude-2, etc. |
| Google AI | ✅ | Gemini Pro, etc. |
| OpenRouter | ✅ | 100+ models |
| Together AI | ✅ | Llama, Mistral, etc. |
| Azure OpenAI | ✅ | GPT-4, etc. |
| AWS Bedrock | ✅ | Claude, Titan, etc. |
| Ollama | ✅ | Local models |

## 📊 Monitoring & Analytics

### Real-time Dashboard
- Current spend vs budget
- Usage trends and forecasts
- Provider performance metrics

### Alert System
- Budget threshold warnings
- Rate limit notifications
- Provider outage alerts

### Export Capabilities
- CSV usage reports
- JSON analytics data
- Integration with BI tools

## 🔐 Security

- **JWT Authentication** with refresh tokens
- **Rate Limiting** per IP and project
- **HTTPS Enforcement** in production
- **Security Headers** (HSTS, CSP, etc.)
- **Input Validation** and SSRF protection

## 🧪 Testing

```bash
# Run all tests
python -m pytest backend/tests/ -v

# Test specific components
python -m pytest backend/tests/test_proxy.py -v
python -m pytest backend/tests/test_security.py -v
python -m pytest backend/tests/test_integration.py -v
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📞 Support

- **Documentation**: https://llmbudget.maxiaworld.app/docs
- **API Reference**: [api-reference.md](./docs/api-reference.md)
- **Email Support**: ceo@maxiaworld.app
- **Status Page**: https://status.maxiaworld.app

## 📄 License

Proprietary - See [Terms](https://maxiaworld.app/terms) for details.

---

Built with ❤️ by [MAXIA Lab](https://maxiaworld.app)