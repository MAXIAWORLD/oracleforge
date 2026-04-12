"""OutreachForge — API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api", tags=["outreach"])


class ScoreRequest(BaseModel):
    email: str
    name: str = ""
    company: str = ""
    title: str = ""


class PersonalizeRequest(BaseModel):
    template: str = Field(..., min_length=1)
    prospect: dict


@router.post("/score")
async def score_prospect(req: ScoreRequest, request: Request) -> dict:
    scorer = request.app.state.lead_scorer
    result = scorer.score(req.email, req.name, req.company, req.title)
    return {"score": result.score, "tier": result.tier, "factors": result.factors}


@router.post("/score/batch")
async def score_batch(prospects: list[ScoreRequest], request: Request) -> dict:
    if len(prospects) > 500:
        raise HTTPException(400, "Maximum 500 prospects per batch")
    scorer = request.app.state.lead_scorer
    results = [
        {"email": p.email, **vars(scorer.score(p.email, p.name, p.company, p.title))}
        for p in prospects
    ]
    results.sort(key=lambda x: -x["score"])
    return {"results": results, "total": len(results)}


@router.post("/personalize")
async def personalize(req: PersonalizeRequest, request: Request) -> dict:
    personalizer = request.app.state.personalizer
    result = personalizer.personalize(req.template, req.prospect)
    variables = personalizer.validate_template(req.template)
    return {"personalized": result, "variables_used": variables}


# ── Email sending ────────────────────────────────────────────────


class SendRequest(BaseModel):
    to_email: str
    subject: str
    body_html: str
    body_text: str = ""


@router.post("/send")
async def send_email(req: SendRequest, request: Request) -> dict:
    """Send a personalised email via SMTP."""
    sender = getattr(request.app.state, "email_sender", None)
    if sender is None:
        raise HTTPException(503, "Email sender not initialised")
    result = sender.send(req.to_email, req.subject, req.body_html, req.body_text)
    if not result.success:
        raise HTTPException(400, result.error)
    return {"sent": True, "message_id": result.message_id}


@router.get("/send/stats")
async def send_stats(request: Request) -> dict:
    sender = getattr(request.app.state, "email_sender", None)
    if sender is None:
        return {"configured": False}
    return sender.stats()
