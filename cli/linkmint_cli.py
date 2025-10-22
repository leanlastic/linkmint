import os, json, typer, requests, webbrowser, pathlib, sys
from dotenv import load_dotenv
import stripe

app = typer.Typer(add_help_option=True, no_args_is_help=True)
load_dotenv()

STRIPE_KEY = os.getenv("STRIPE_SECRET_KEY","")
PRINTFUL_KEY = os.getenv("PRINTFUL_API_KEY","")
BASE_URL = os.getenv("BASE_URL","http://localhost:8000")

if STRIPE_KEY:
    stripe.api_key = STRIPE_KEY

@app.command("stripe:set-key")
def stripe_set_key(key: str):
    p = pathlib.Path(".env")
    text = p.read_text() if p.exists() else ""
    lines = []
    found = False
    for line in text.splitlines():
        if line.startswith("STRIPE_SECRET_KEY="):
            lines.append(f"STRIPE_SECRET_KEY={key}")
            found = True
        else:
            lines.append(line)
    if not found:
        lines.append(f"STRIPE_SECRET_KEY={key}")
    p.write_text("\n".join(lines) + "\n")
    typer.echo("Updated .env STRIPE_SECRET_KEY")

@app.command("printful:set-key")
def printful_set_key(key: str):
    p = pathlib.Path(".env")
    text = p.read_text() if p.exists() else ""
    lines = []
    found = False
    for line in text.splitlines():
        if line.startswith("PRINTFUL_API_KEY="):
            lines.append(f"PRINTFUL_API_KEY={key}")
            found = True
        else:
            lines.append(line)
    if not found:
        lines.append(f"PRINTFUL_API_KEY={key}")
    p.write_text("\n".join(lines) + "\n")
    typer.echo("Updated .env PRINTFUL_API_KEY")

@app.command("printful:list")
def printful_list(search: str = typer.Option("", "--search")):
    if not PRINTFUL_KEY:
        typer.echo("PRINTFUL_API_KEY missing")
        raise typer.Exit(1)
    # Minimal list: catalog products endpoint
    r = requests.get("https://api.printful.com/store/products", headers={"Authorization": f"Bearer {PRINTFUL_KEY}"}, timeout=20)
    r.raise_for_status()
    data = r.json().get("result", [])
    for p in data:
        if search.lower() in (p.get("name") or "").lower():
            typer.echo(f"{p.get('id')}: {p.get('name')}")

@app.command("printful:import")
def printful_import(printful_product_id: int, price_cents: int = typer.Option(..., "--price"), currency: str = typer.Option("EUR", "--currency"), theme: str = typer.Option("default", "--theme")):
    if not PRINTFUL_KEY or not STRIPE_KEY:
        typer.echo("PRINTFUL_API_KEY or STRIPE_SECRET_KEY missing")
        raise typer.Exit(1)
    pr = requests.get(f"https://api.printful.com/store/products/{printful_product_id}", headers={"Authorization": f"Bearer {PRINTFUL_KEY}"}, timeout=20)
    pr.raise_for_status()
    prod = pr.json().get("result", {})
    title = prod.get("name","Imported Product")
    image = (prod.get("sync_product") or {}).get("thumbnail_url") or ""
    slug = title.lower().replace(" ","-").replace("/","-")
    sprod = stripe.Product.create(
        name=title,
        description=title,
        images=[image] if image else [],
        metadata={
            "slug": slug,
            "og_title": title,
            "og_description": title,
            "og_image": image,
            "printful_product_id": str(printful_product_id),
            "theme": theme,
            "published": "false",
        },
    )
    price = stripe.Price.create(
        unit_amount=price_cents,
        currency=currency.lower(),
        product=sprod.id
    )
    # set default price
    stripe.Product.modify(sprod.id, default_price=price.id)
    url = f"{BASE_URL}/p/{slug}"
    typer.echo(f"Imported → Stripe Product {sprod.id}, Price {price.id}")
    typer.echo(f"Preview: {url} (unpublished)")
    return

@app.command("product:publish")
def product_publish(slug: str):
    res = stripe.Product.search(query=f"metadata['slug']:'{slug}'")
    target = None
    for p in res.auto_paging_iter():
        if p.metadata.get("slug")==slug:
            target = p; break
    if not target:
        typer.echo("Not found"); raise typer.Exit(1)
    md = dict(target.metadata)
    md["published"]="true"
    stripe.Product.modify(target.id, metadata=md, active=True)
    typer.echo(f"Published: {slug} → {BASE_URL}/p/{slug}")

@app.command("product:unpublish")
def product_unpublish(slug: str):
    res = stripe.Product.search(query=f"metadata['slug']:'{slug}'")
    target = None
    for p in res.auto_paging_iter():
        if p.metadata.get("slug")==slug:
            target = p; break
    if not target:
        typer.echo("Not found"); raise typer.Exit(1)
    md = dict(target.metadata)
    md["published"]="false"
    stripe.Product.modify(target.id, metadata=md)
    typer.echo(f"Unpublished: {slug}")

@app.command("product:list")
def product_list(published: bool = typer.Option(False, "--published"), theme: str = typer.Option("", "--theme")):
    q = "active:'true'"
    res = stripe.Product.search(query=q)
    for p in res.auto_paging_iter():
        md = p.metadata or {}
        if theme and md.get("theme") != theme: 
            continue
        if published and md.get("published") != "true":
            continue
        slug = md.get("slug","")
        price_id = p.default_price if isinstance(p.default_price, str) else (p.default_price.id if p.default_price else "")
        print(f"{slug:24} {p.id:24} price:{price_id} published:{md.get('published')} theme:{md.get('theme','default')}")

@app.command("link:open")
def link_open(slug: str):
    webbrowser.open(f"{BASE_URL}/p/{slug}")

@app.command("stats")
def stats(days: int = typer.Option(30, "--since")):
    from datetime import datetime, timedelta, timezone
    end = int(datetime.now(timezone.utc).timestamp())
    start = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())
    charges = stripe.Charge.list(created={"gte": start, "lte": end}, limit=100)
    total = sum(c["amount"] for c in charges.auto_paging_iter() if c["paid"] and not c["refunded"])
    print(f"GMV {days}d: {total/100:.2f}")

if __name__ == "__main__":
    app()
