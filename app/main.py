import os, secrets, time
from fastapi import FastAPI, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from itsdangerous import TimestampSigner, BadSignature
from dotenv import load_dotenv
from . import stripe_utils
from .email_providers import build_provider

load_dotenv()

app = FastAPI(title="LinkMint")
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

signer = TimestampSigner(os.getenv("PREVIEW_TOKEN_SECRET", "change_me"))
email_provider = build_provider()

def _meta_from_product(prod):
    md = prod.metadata or {}
    return {
        "title": prod.name,
        "description": md.get("og_description") or prod.description or "",
        "og_title": md.get("og_title") or prod.name,
        "og_description": md.get("og_description") or prod.description or "",
        "og_image": md.get("og_image") or (prod.images[0] if getattr(prod, "images", []) else ""),
        "slug": md.get("slug",""),
        "theme": md.get("theme","default"),
        "published": md.get("published","true"),
    }

@app.get("/healthz", response_class=PlainTextResponse)
def healthz():
    return "ok"

@app.get("/p/{slug}", response_class=HTMLResponse)
def product_page(request: Request, slug: str, preview: str | None = None, success: str | None = None, cancel: str | None = None):
    prod = stripe_utils.find_product_by_slug(slug)
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found")
    meta = _meta_from_product(prod)
    if meta["published"] != "true":
        if not preview:
            raise HTTPException(status_code=404, detail="Product not published")
        try:
            signer.unsign(preview, max_age=3600)
        except BadSignature:
            raise HTTPException(status_code=403, detail="Invalid preview token")
    price_id = stripe_utils.default_price_for_product(prod)
    if not price_id:
        raise HTTPException(status_code=400, detail="No active price for product")
    return templates.TemplateResponse(
        f"themes/{meta['theme']}/product.html",
        {
            "request": request,
            "meta": meta,
            "product": prod,
            "price_id": price_id,
            "success": success,
            "cancel": cancel,
        },
    )

@app.post("/api/checkout/session")
async def create_session(slug: str = Form(...), email: str | None = Form(None)):
    prod = stripe_utils.find_product_by_slug(slug)
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found")
    price_id = stripe_utils.default_price_for_product(prod)
    if not price_id:
        raise HTTPException(status_code=400, detail="No price configured")
    order_public_id = secrets.token_urlsafe(8)
    url = stripe_utils.create_checkout_session(
        slug=slug,
        price_id=price_id,
        customer_email=email,
        metadata={"product_slug": slug, "order_public_id": order_public_id},
    )
    return RedirectResponse(url, status_code=303)

@app.post("/api/stripe/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig = request.headers.get("stripe-signature","")
    try:
        event = stripe_utils.verify_webhook(sig, payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid signature")
    t = event["type"]
    data = event["data"]["object"]

    # Order confirmed → send transactional email
    if t == "checkout.session.completed":
        customer_email = data.get("customer_details",{}).get("email")
        line_items = []  # optional: fetch items if needed
        slug = (data.get("metadata") or {}).get("product_slug","")
        if customer_email and slug:
            subject = f"Your order is confirmed"
            html = f"<p>Thanks for your purchase of <strong>{slug}</strong>.</p>"
            try:
                email_provider.send(customer_email, subject, html, text=f"Order confirmed for {slug}")
            except Exception:
                pass

    if t == "charge.refunded":
        email = data.get("billing_details",{}).get("email")
        if email:
            try:
                email_provider.send(email, "Your refund is completed", "<p>Your refund has been processed.</p>")
            except Exception:
                pass

    return {"ok": True}

@app.get("/self")
def portal(request: Request):
    # Use last completed session stored in cookie? For MVP, require ?customer_id=
    from fastapi import Query
    # simpler: ?customer_id=cus_xxx
    return RedirectResponse(url="/", status_code=302)

@app.get("/preview-token/{slug}")
def preview_token(slug: str):
    token = signer.sign(slug).decode("utf-8")
    return {"preview": token}
