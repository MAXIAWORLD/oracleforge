# GuardForge Marketing Site

Static landing page for GuardForge. Deploys to Vercel (or any static host) for free.

## Deploy to Vercel

```bash
# One-time
npm install -g vercel

# Deploy
cd guardforge/marketing
vercel --prod
```

Or push to a GitHub repo, connect to Vercel, and auto-deploys on every push.

## Local preview

```bash
# Any static HTTP server works
python -m http.server 8000
# then open http://localhost:8000
```

## What's here

- `index.html` — single-file landing page (~700 lines of HTML+CSS, zero JS dependencies, zero build step)
- `vercel.json` — security headers for the static deployment
- No framework, no bundler, no build — edit and deploy

## Content

- **Hero**: one-line-change positioning + interactive code sample
- **Features**: 6 cards (reversible tokenization, 13 jurisdictions, compliance reports, 17 entity types, <10ms latency, webhooks)
- **Compare**: table vs Presidio / Nightfall / Private AI
- **Pricing**: Free / Starter 39€ / Pro 129€ / Business 349€ + Enterprise + Self-hosted CTA
- **Final CTA**: fear-driven (GDPR 4% fines, EU AI Act criminal liability)

## TODO before launch

1. Replace `#` href placeholders with real LemonSqueezy product URLs once created
2. Add real logos of early customers (currently absent — logo wall placeholder is intentional)
3. Add testimonial quotes from beta users (once obtained)
4. Configure custom domain in Vercel settings
5. Hook up Google Analytics or Plausible for privacy-friendly tracking
6. Add OG image (currently only text-based OG tags)

## Analytics philosophy

No Google Analytics in the initial version. Use Plausible, Fathom, or Umami (privacy-friendly) once traffic justifies it. We sell privacy — can't use surveillance analytics.
