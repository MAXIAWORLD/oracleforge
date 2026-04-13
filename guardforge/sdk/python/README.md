# GuardForge Python SDK

> **Drop-in PII redaction for OpenAI, Anthropic, and other LLM SDKs.**
> Replace one import line and PII never leaves your infrastructure.

[![PyPI](https://img.shields.io/badge/pypi-guardforge-blue)]()
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)]()
[![License](https://img.shields.io/badge/license-Proprietary-red)]()

---

## What it does

The GuardForge SDK is a thin wrapper around official LLM SDKs (`openai`, `anthropic`) that automatically:

1. **Detects PII** in every prompt before it leaves your infrastructure
2. **Replaces PII with reversible tokens** (e.g. `[PERSON_NAME_a3f2]`)
3. **Sends the safe text** to OpenAI / Anthropic
4. **Restores the original values** in the response so your end user sees the real data

Your LLM provider never sees raw PII. Your application code doesn't change.

---

## Installation

```bash
pip install guardforge[openai]            # for OpenAI only
pip install guardforge[anthropic]         # for Anthropic only
pip install guardforge[all]               # for both
```

You also need a running [GuardForge backend](https://github.com/maxia-lab/guardforge) (cloud or self-hosted).

---

## Quick start

### OpenAI

```python
# Before
# from openai import OpenAI

# After
from guardforge import OpenAI

client = OpenAI(api_key="sk-...")     # OpenAI key, same as before
response = client.chat.completions.create(
    model="gpt-4",
    messages=[
        {"role": "user", "content": "Hi, my name is Jean Dupont and my IBAN is FR7630006000011234567890189"}
    ],
)

print(response.choices[0].message.content)
# Output: "Hello Jean Dupont, your IBAN FR7630006000011234567890189 is confirmed."
# But OpenAI saw: "Hello [PERSON_NAME_a3f2], your IBAN [IBAN_b491] is confirmed."
```

### Anthropic

```python
from guardforge import Anthropic

client = Anthropic(api_key="sk-ant-...")
response = client.messages.create(
    model="claude-sonnet-4-5",
    max_tokens=1024,
    messages=[
        {"role": "user", "content": "My SIRET is 73282932000074"}
    ],
)

print(response.content[0].text)
# Real SIRET visible to the end user, but Anthropic only saw [SIRET_FR_xxxx]
```

---

## Configuration

The SDK needs to know how to reach your GuardForge backend. Set environment variables:

```bash
export GUARDFORGE_API_URL=https://api.guardforge.io      # or http://localhost:8004 for self-hosted
export GUARDFORGE_API_KEY=your-secret-key
```

Or pass them explicitly:

```python
client = OpenAI(
    api_key="sk-...",
    guardforge_url="http://localhost:8004",
    guardforge_api_key="your-secret-key",
)
```

Or inject a pre-configured client:

```python
from guardforge import OpenAI, GuardForgeClient

gf = GuardForgeClient(url="http://localhost:8004", api_key="...")
client = OpenAI(api_key="sk-...", guardforge_client=gf)
```

---

## What gets tokenized

Every chat message with a string `content` is tokenized. The SDK detects 17 entity types out of the box:

- **Personal**: email, phone, person names (with title heuristic)
- **Financial**: credit card (Luhn-validated), IBAN, French RIB
- **National IDs**: SSN US/FR, SIRET/SIREN (FR), Steuer-ID (DE), DNI/NIE (ES), Codice Fiscale (IT), passport, generic
- **Dates**: dates of birth
- **Network**: IPv4

The exact policy applied is configured server-side via the GuardForge backend.

---

## What does NOT get tokenized (yet)

These pass through untouched in v0.1.0:

- **Multimodal content** (image_url, audio blocks) — only text fields are scanned
- **Tool calls / function arguments** — JSON arguments to tools
- **System prompts in OpenAI** — wrapped only for Anthropic; OpenAI system messages need explicit user message wrapping
- **Streaming responses** (`stream=True`) — tokens flow through, but detokenization is bypassed (TODO for v0.2)
- **Async clients** (`openai.AsyncOpenAI`, `anthropic.AsyncAnthropic`) — use sync versions for now

---

## How it works under the hood

1. Your `chat.completions.create(messages=...)` call goes through a `_CompletionsProxy`.
2. The proxy iterates over `messages`, sends each text content to `POST /api/tokenize` on the GuardForge backend.
3. The backend detects PII, replaces with tokens, encrypts the mapping in the vault under a `session_id`.
4. The proxy reconstructs the messages list with tokenized content and calls the real OpenAI SDK.
5. OpenAI returns a response containing tokens (it never saw real PII).
6. The proxy posts the response text to `POST /api/detokenize` with the same `session_id`.
7. Original PII is restored in the response object before it returns to your code.

The whole flow is synchronous and adds typically 50-150ms per call.

---

## Error handling

If the GuardForge backend is unreachable:
- **Tokenize fails** → raises `guardforge.GuardForgeError`. Your call is aborted (fail-closed by default).
- **Detokenize fails** → response is returned with tokens still in place (best-effort, never breaks user flow).

```python
from guardforge import OpenAI, GuardForgeError

try:
    response = client.chat.completions.create(...)
except GuardForgeError as e:
    print(f"GuardForge backend unreachable: {e}")
    # Fallback: call OpenAI directly without protection (NOT RECOMMENDED for prod)
```

---

## Testing your integration

```python
from guardforge import GuardForgeClient

gf = GuardForgeClient(url="http://localhost:8004", api_key="...")
print(gf.health())
# {'status': 'ok', 'version': '0.1.0', 'vault_entries': 0, 'policies_loaded': 16}
```

---

## License

Proprietary. See LICENSE in the parent repository.

---

## Support

- Documentation: https://maxialab.com/guardforge/docs
- Issues: GitHub Issues
- Email: support@maxialab.com
