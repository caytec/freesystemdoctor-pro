"""
FreeSystemDoctor Pro — Activation Server

FastAPI app that:
1. Receives Stripe/Paddle/Przelewy24 webhooks → generates license key → emails it
2. Activates / deactivates license keys (called by the desktop app)
3. Tracks device-binding (machine_id → key)
4. Admin endpoints for revenue stats and key management

Deploy targets (all under 5-min setup):
- Fly.io        (free tier: 256 MB RAM, 3 GB volume — enough for 100k licenses)
- Railway      (free tier: $5/mo of usage credits)
- Cloudflare Workers + D1 (truly free, requires porting to TypeScript)

Run locally:
    uvicorn app.main:app --reload --port 8000

Env vars (set in deploy platform):
    LICENSE_HMAC_SECRET      — random 32-byte hex string
    STRIPE_WEBHOOK_SECRET    — whsec_... from Stripe dashboard
    PADDLE_PUBLIC_KEY        — Paddle public RSA key for signature verification
    RESEND_API_KEY           — re_... from resend.com
    ADMIN_TOKEN              — bearer token for /admin endpoints
    DATABASE_URL             — sqlite:///./fsd.db   or postgres://...
"""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException, Header, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy import (
    Column, String, Integer, DateTime, Float, create_engine, select
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from .keys import generate_key, validate_key_format, parse_key
from .email_service import send_license_email, send_invoice_email


# ── config ───────────────────────────────────────────────────────────────────

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./fsd.db")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
PADDLE_PUBLIC_KEY = os.environ.get("PADDLE_PUBLIC_KEY", "")
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")


# ── DB ───────────────────────────────────────────────────────────────────────

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class License(Base):
    __tablename__ = "licenses"
    key             = Column(String, primary_key=True)
    tier            = Column(String, nullable=False)              # pro | ultimate
    email           = Column(String, nullable=False, index=True)
    expiry          = Column(DateTime, nullable=True)             # null = lifetime
    devices_used    = Column(Integer, default=0)
    devices_max    = Column(Integer, default=3)
    payment_provider = Column(String)                              # stripe | paddle | przelewy24
    payment_amount  = Column(Float)
    payment_currency = Column(String, default="PLN")
    transaction_id  = Column(String, index=True)
    created_at      = Column(DateTime, default=datetime.utcnow)
    revoked         = Column(Integer, default=0)


class MachineBinding(Base):
    __tablename__ = "machines"
    id              = Column(Integer, primary_key=True, autoincrement=True)
    license_key     = Column(String, index=True, nullable=False)
    machine_id      = Column(String, index=True, nullable=False)
    hostname        = Column(String)
    last_seen       = Column(DateTime, default=datetime.utcnow)
    activated_at    = Column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── schemas ──────────────────────────────────────────────────────────────────

class ActivateRequest(BaseModel):
    key: str
    machine_id: str
    hostname: Optional[str] = ""


class ActivateResponse(BaseModel):
    valid: bool
    tier: str = "free"
    expiry_iso: str = ""
    devices_used: int = 0
    devices_max: int = 0
    error: str = ""


class DeactivateRequest(BaseModel):
    key: str
    machine_id: str


class VerifyRequest(BaseModel):
    key: str
    machine_id: str


# ── app ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="FreeSystemDoctor Pro — Activation Server",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://caytec.github.io",
                   "https://freesystemdoctor.pl",
                   "https://pro.freesystemdoctor.pl"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"service": "fsd-pro-activation", "status": "ok"}


@app.get("/healthz")
def healthz():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


# ── /v1/activate ─────────────────────────────────────────────────────────────

@app.post("/v1/activate", response_model=ActivateResponse)
def activate(req: ActivateRequest, db: Session = Depends(get_db)):
    if not validate_key_format(req.key):
        return ActivateResponse(valid=False, error="Niepoprawny format klucza")

    lic = db.get(License, req.key)
    if not lic:
        return ActivateResponse(valid=False, error="Klucz nie istnieje")
    if lic.revoked:
        return ActivateResponse(valid=False, error="Klucz został cofnięty")
    if lic.expiry and lic.expiry < datetime.utcnow():
        return ActivateResponse(valid=False, error="Licencja wygasła")

    # Check if this machine is already bound
    existing = db.scalar(
        select(MachineBinding).where(
            MachineBinding.license_key == req.key,
            MachineBinding.machine_id == req.machine_id,
        )
    )

    if existing:
        existing.last_seen = datetime.utcnow()
        db.commit()
    else:
        # New device — check device limit
        if lic.devices_used >= lic.devices_max:
            return ActivateResponse(
                valid=False,
                error=f"Przekroczono limit urządzeń ({lic.devices_max}). "
                      f"Cofnij licencję na innym urządzeniu lub upgrade do wyższego tieru.",
                tier=lic.tier,
                devices_used=lic.devices_used,
                devices_max=lic.devices_max,
            )
        db.add(MachineBinding(
            license_key=req.key,
            machine_id=req.machine_id,
            hostname=req.hostname,
        ))
        lic.devices_used += 1
        db.commit()

    return ActivateResponse(
        valid=True,
        tier=lic.tier,
        expiry_iso=lic.expiry.isoformat() if lic.expiry else "",
        devices_used=lic.devices_used,
        devices_max=lic.devices_max,
    )


@app.post("/v1/deactivate")
def deactivate(req: DeactivateRequest, db: Session = Depends(get_db)):
    binding = db.scalar(
        select(MachineBinding).where(
            MachineBinding.license_key == req.key,
            MachineBinding.machine_id == req.machine_id,
        )
    )
    if not binding:
        raise HTTPException(404, "Urządzenie nie aktywowane")
    db.delete(binding)
    lic = db.get(License, req.key)
    if lic and lic.devices_used > 0:
        lic.devices_used -= 1
    db.commit()
    return {"ok": True}


# ── webhooks ─────────────────────────────────────────────────────────────────

@app.post("/webhooks/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Receive Stripe checkout.session.completed event → create license."""
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")

    try:
        import stripe
        event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
    except Exception as e:
        raise HTTPException(400, f"Webhook verification failed: {e}")

    if event["type"] != "checkout.session.completed":
        return {"ignored": True}

    session = event["data"]["object"]
    email = session.get("customer_email") or session["customer_details"]["email"]
    metadata = session.get("metadata", {})
    tier = metadata.get("tier", "pro")              # pro | ultimate
    period = metadata.get("period", "yearly")       # yearly | lifetime
    amount = session.get("amount_total", 0) / 100.0
    currency = (session.get("currency") or "PLN").upper()

    license_key = _provision_license(
        db, tier=tier, period=period, email=email,
        provider="stripe", amount=amount, currency=currency,
        transaction_id=session["id"],
    )

    return {"created": True, "key_prefix": license_key[:12]}


@app.post("/webhooks/paddle")
async def paddle_webhook(request: Request, db: Session = Depends(get_db)):
    """Receive Paddle transaction.completed event → create license."""
    form = await request.form()
    # TODO: verify Paddle signature with PADDLE_PUBLIC_KEY (RSA-SHA1)
    email = form.get("email", "")
    tier = form.get("custom_tier", "pro")
    period = form.get("custom_period", "yearly")
    amount = float(form.get("sale_gross", 0))

    license_key = _provision_license(
        db, tier=tier, period=period, email=email,
        provider="paddle", amount=amount, currency="USD",
        transaction_id=form.get("order_id", ""),
    )
    return {"created": True}


@app.post("/webhooks/przelewy24")
async def p24_webhook(request: Request, db: Session = Depends(get_db)):
    """Receive Przelewy24 transaction notification."""
    data = await request.json()
    # TODO: verify P24 SHA-384 signature
    email = data.get("email", "")
    tier = data.get("tier", "pro")
    period = data.get("period", "yearly")
    amount = float(data.get("amount", 0)) / 100.0

    license_key = _provision_license(
        db, tier=tier, period=period, email=email,
        provider="przelewy24", amount=amount, currency="PLN",
        transaction_id=data.get("orderId", ""),
    )
    return {"created": True}


def _provision_license(
    db: Session, *, tier: str, period: str, email: str,
    provider: str, amount: float, currency: str, transaction_id: str,
) -> str:
    """Generate key, persist, email it."""
    # Idempotency: if we already issued for this transaction, return existing
    existing = db.scalar(
        select(License).where(License.transaction_id == transaction_id)
    )
    if existing:
        return existing.key

    # Generate cryptographically signed key
    devices_max = 5 if tier == "ultimate" else 3
    year = datetime.utcnow().year
    key = generate_key(tier=tier, year=year)

    expiry = None
    if period != "lifetime":
        expiry = datetime.utcnow() + timedelta(days=365)

    lic = License(
        key=key, tier=tier, email=email, expiry=expiry,
        devices_used=0, devices_max=devices_max,
        payment_provider=provider, payment_amount=amount,
        payment_currency=currency, transaction_id=transaction_id,
    )
    db.add(lic)
    db.commit()

    # Send email (async — log failure but don't block webhook response)
    try:
        send_license_email(
            to=email, key=key, tier=tier, period=period,
            expiry_iso=expiry.isoformat() if expiry else "",
            devices_max=devices_max,
        )
        send_invoice_email(
            to=email, tier=tier, period=period,
            amount=amount, currency=currency,
            transaction_id=transaction_id,
        )
    except Exception as e:
        print(f"Email delivery failed for {email}: {e}")
        # In production: push to retry queue

    return key


# ── admin ────────────────────────────────────────────────────────────────────

def require_admin(authorization: str = Header(default="")):
    if not ADMIN_TOKEN or authorization != f"Bearer {ADMIN_TOKEN}":
        raise HTTPException(401, "Unauthorized")


@app.get("/admin/stats", dependencies=[Depends(require_admin)])
def admin_stats(db: Session = Depends(get_db)):
    from sqlalchemy import func
    total = db.scalar(select(func.count()).select_from(License)) or 0
    pro = db.scalar(select(func.count()).where(License.tier == "pro")) or 0
    ult = db.scalar(select(func.count()).where(License.tier == "ultimate")) or 0
    revenue = db.scalar(select(func.sum(License.payment_amount))) or 0
    devices = db.scalar(select(func.count()).select_from(MachineBinding)) or 0

    return {
        "licenses_total": total,
        "licenses_pro": pro,
        "licenses_ultimate": ult,
        "active_devices": devices,
        "revenue_total_pln": round(revenue, 2),
        "generated_at": datetime.utcnow().isoformat(),
    }


@app.get("/admin/licenses", dependencies=[Depends(require_admin)])
def admin_licenses(limit: int = 100, db: Session = Depends(get_db)):
    rows = db.scalars(
        select(License).order_by(License.created_at.desc()).limit(limit)
    ).all()
    return [
        {
            "key": r.key, "tier": r.tier, "email": r.email,
            "expiry": r.expiry.isoformat() if r.expiry else None,
            "devices": f"{r.devices_used}/{r.devices_max}",
            "amount": r.payment_amount, "currency": r.payment_currency,
            "provider": r.payment_provider, "created": r.created_at.isoformat(),
            "revoked": bool(r.revoked),
        }
        for r in rows
    ]


@app.post("/admin/licenses/{key}/revoke", dependencies=[Depends(require_admin)])
def admin_revoke(key: str, db: Session = Depends(get_db)):
    lic = db.get(License, key)
    if not lic:
        raise HTTPException(404)
    lic.revoked = 1
    db.commit()
    return {"revoked": True}
