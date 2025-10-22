import os, stripe
from typing import Any, Dict

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")

def build_success_url(slug: str, order_public_id: str) -> str:
    template = os.getenv("STRIPE_SUCCESS_URL_BASE", f"{os.getenv('BASE_URL','http://localhost:8000')}/p/{{slug}}?success=1&op={{order_public_id}}")
    return template.replace("{{slug}}", slug).replace("{{order_public_id}}", order_public_id)

def build_cancel_url(slug: str) -> str:
    template = os.getenv("STRIPE_CANCEL_URL_BASE", f"{os.getenv('BASE_URL','http://localhost:8000')}/p/{{slug}}?cancel=1")
    return template.replace("{{slug}}", slug)

def create_checkout_session(slug: str, price_id: str, customer_email: str | None = None, metadata: Dict[str, str] | None = None) -> str:
    success_url = build_success_url(slug, metadata.get("order_public_id") if metadata else "na")
    cancel_url = build_cancel_url(slug)
    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        customer_email=customer_email,
        metadata=metadata or {},
    )
    return session.url

def verify_webhook(sig_header: str, payload: bytes):
    wh_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    return stripe.Webhook.construct_event(payload=payload, sig_header=sig_header, secret=wh_secret)

def find_product_by_slug(slug: str):
    # Stripe doesn't index metadata; filter client-side
    # Fetch all active products and filter client-side
    products = stripe.Product.list(active=True)
    for p in products.auto_paging_iter():
        if p.metadata.get("slug") == slug:
            return p
    return None

def default_price_for_product(product) -> str | None:
    # Prefer default_price if active, else first active price
    dp = product.get("default_price") if isinstance(product, dict) else getattr(product, "default_price", None)
    price = dp if isinstance(dp, str) else (dp.get("id") if dp else None)
    if price:
        pr = stripe.Price.retrieve(price)
        if pr.active:
            return pr.id
    # fallback
    prices = stripe.Price.list(product=product.id, active=True, limit=10)
    if prices.data:
        return prices.data[0].id
    return None

def create_billing_portal_session(customer_id: str, return_url: str) -> str:
    session = stripe.billing_portal.Session.create(customer=customer_id, return_url=return_url)
    return session.url

def archive_price(price_id: str):
    stripe.Price.modify(price_id, active=False)
