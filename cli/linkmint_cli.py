import os, json, typer, requests, webbrowser, pathlib, sys
from dotenv import load_dotenv
import stripe
from rich.console import Console
from rich.table import Table
from rich.layout import Layout
from rich.panel import Panel

# Add parent directory to sys.path for module imports
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from app import stripe_utils

console = Console()

app = typer.Typer(
    add_help_option=True,
    no_args_is_help=True,
    help="Linkmint CLI: Manage your Printful and Stripe products."
)
load_dotenv()

STRIPE_KEY = os.getenv("STRIPE_SECRET_KEY", "")
PRINTFUL_KEY = os.getenv("PRINTFUL_API_KEY", "")
PRINTFUL_STORE_ID = os.getenv("PRINTFUL_STORE_ID", "")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

if STRIPE_KEY:
    stripe.api_key = STRIPE_KEY

@app.command("stripe:set-key")
def stripe_set_key(key: str):
    """Sets the Stripe secret key in the .env file.

    This key is essential for authenticating with the Stripe API.
    """
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
    """Sets the Printful API key in the .env file.

    This key is required for authenticating with the Printful API.
    """
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

@app.command("printful:set-store-id")
def printful_set_store_id(store_id: str):
    """Sets the Printful Store ID in the .env file.

    This ID is used to identify your specific Printful store when making API requests.
    """
    p = pathlib.Path(".env")
    text = p.read_text() if p.exists() else ""
    lines = []
    found = False
    for line in text.splitlines():
        if line.startswith("PRINTFUL_STORE_ID="):
            lines.append(f"PRINTFUL_STORE_ID={store_id}")
            found = True
        else:
            lines.append(line)
    if not found:
        lines.append(f"PRINTFUL_STORE_ID={store_id}")
    p.write_text("\n".join(lines) + "\n")
    typer.echo("Updated .env PRINTFUL_STORE_ID")

def _get_stripe_products():
    if not STRIPE_KEY:
        typer.echo("STRIPE_SECRET_KEY missing")
        raise typer.Exit(1)
    return stripe.Product.search(query="active:'true'").auto_paging_iter()

def _get_printful_products(store_id: str = PRINTFUL_STORE_ID):
    if not PRINTFUL_KEY:
        typer.echo("PRINTFUL_API_KEY missing")
        raise typer.Exit(1)
    if not store_id:
        typer.echo("PRINTFUL_STORE_ID missing. Please set it in .env or provide with --store-id.")
        raise typer.Exit(1)
    r = requests.get("https://api.printful.com/store/products", headers={"Authorization": f"Bearer {PRINTFUL_KEY}", "X-PF-Store-Id": store_id}, timeout=20)
    r.raise_for_status()
    return r.json().get("result", [])

def _get_printful_product_details(printful_product_id: int, store_id: str):
    if not PRINTFUL_KEY:
        typer.echo("PRINTFUL_API_KEY missing")
        raise typer.Exit(1)
    if not store_id:
        typer.echo("PRINTFUL_STORE_ID missing. Please set it in .env or provide with --store-id.")
        raise typer.Exit(1)
    r = requests.get(f"https://api.printful.com/store/products/{printful_product_id}", headers={"Authorization": f"Bearer {PRINTFUL_KEY}", "X-PF-Store-Id": store_id}, timeout=20)
    r.raise_for_status()
    return r.json().get("result", {})

@app.command("printful:product")
def printful_product(printful_product_id: int, store_id: str = typer.Option(PRINTFUL_STORE_ID, "--store-id")):
    """Displays all details for a specific Printful product from your store.

    The product is identified by its Printful product ID.
    """
    product_details = _get_printful_product_details(printful_product_id, store_id)
    console.print(Panel(json.dumps(product_details, indent=2), title=f"[bold green]Details for Printful Product ID: {printful_product_id}[/bold green]", border_style="green"))

@app.command("printful:ui")
def printful_ui(store_id: str = typer.Option(PRINTFUL_STORE_ID, "--store-id")):
    """Launches an interactive terminal UI to manage Printful and Stripe products.

    Displays both live products from Stripe and available products from your Printful store.
    """
    if not store_id:
        typer.echo("PRINTFUL_STORE_ID missing. Please set it in .env or provide with --store-id.")
        raise typer.Exit(1)
    console.print("[bold green]Printful UI[/bold green]")

    # Live Products View
    console.print("\n[bold blue]Live Products (Stripe)[/bold blue]")
    try:
        stripe_products = _get_stripe_products()
        
        live_products_table = Table(title="Live Products")
        live_products_table.add_column("ID", style="cyan", no_wrap=True)
        live_products_table.add_column("Name", style="magenta")
        live_products_table.add_column("Published", style="green")
        live_products_table.add_column("Theme", style="yellow")

        found_live_products = False
        for p in stripe_products:
            md = p.metadata or {}
            if md.get("published") == "true":
                found_live_products = True
                live_products_table.add_row(
                    p.id,
                    p.name,
                    md.get("published", "false"),
                    md.get("theme", "default"),
                )
        
        if not found_live_products:
            console.print("No live products found in Stripe.")
        else:
            console.print(live_products_table)

    except Exception as e:
        console.print(f"[bold red]Error fetching Stripe products:[/bold red] {e}")

    # Available Printful Products View
    console.print("\n[bold blue]Available Printful Products (Printful Store)[/bold blue]")
    try:
        printful_products = _get_printful_products(store_id)
        if not printful_products:
            console.print("No products found in your Printful store.")
            return

        table = Table(title="Printful Products")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Name", style="magenta")
        table.add_column("Variants", justify="right", style="green")

        for p in printful_products:
            table.add_row(str(p.get("id")), p.get("name", "N/A"), str(p.get("variant_count", "N/A")))
        
        console.print(table)

    except requests.exceptions.HTTPError as e:
        console.print(f"[bold red]Error fetching Printful products:[/bold red] {e}")
    except Exception as e:
        console.print(f"[bold red]An unexpected error occurred:[/bold red] {e}")

@app.command("printful:list")
def printful_list(search: str = typer.Option("", "--search"), store_id: str = typer.Option(PRINTFUL_STORE_ID, "--store-id")):
    """Lists products from your Printful store.

    Optionally filters products by a search term.
    """
    if not PRINTFUL_KEY:
        typer.echo("PRINTFUL_API_KEY missing")
        raise typer.Exit(1)
    if not store_id:
        typer.echo("PRINTFUL_STORE_ID missing. Please set it in .env or provide with --store-id.")
        raise typer.Exit(1)
    r = requests.get("https://api.printful.com/store/products", headers={"Authorization": f"Bearer {PRINTFUL_KEY}", "X-PF-Store-Id": store_id}, timeout=20)
    r.raise_for_status()
    data = r.json().get("result", [])
    for p in data:
        if search.lower() in (p.get("name") or "").lower():
            typer.echo(f"{p.get('id')}: {p.get('name')}")

@app.command("printful:import")
def printful_import(printful_product_id: int, currency: str = typer.Option("EUR", "--currency"), theme: str = typer.Option("default", "--theme"), store_id: str = typer.Option(PRINTFUL_STORE_ID, "--store-id")):
    """Imports a Printful product into Stripe, creating a new Stripe product and price.

    The retail price is automatically derived from the Printful product's first variant.
    """
    if not PRINTFUL_KEY or not STRIPE_KEY:
        typer.echo("PRINTFUL_API_KEY or STRIPE_SECRET_KEY missing")
        raise typer.Exit(1)
    if not store_id:
        typer.echo("PRINTFUL_STORE_ID missing. Please set it in .env or provide with --store-id.")
        raise typer.Exit(1)

    prod_details = _get_printful_product_details(printful_product_id, store_id)
    if not prod_details:
        typer.echo(f"Could not find Printful product with ID {printful_product_id}")
        raise typer.Exit(1)

    # Extract retail_price from the first sync_variant
    retail_price = None
    if prod_details.get("sync_variants"):
        first_variant = prod_details["sync_variants"][0]
        retail_price = first_variant.get("retail_price")

    if not retail_price:
        typer.echo(f"Could not determine retail price for Printful product ID {printful_product_id}. Please provide it manually.")
        raise typer.Exit(1)

    try:
        price_cents = int(float(retail_price) * 100)
    except ValueError:
        typer.echo(f"Invalid retail price format: {retail_price}")
        raise typer.Exit(1)

    title = prod_details.get("name","Imported Product")
    image = ""
    if prod_details.get("sync_variants") and prod_details["sync_variants"][0].get("product"):
        image = prod_details["sync_variants"][0]["product"].get("image", "")
    slug = title.lower().replace(" ","-").replace("/", "-")
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
    typer.echo(f"Debug: sprod.id={sprod.id}, price.id={price.id}")
    typer.echo(f"Imported → Stripe Product {sprod.id}, Price {price.id}")
    typer.echo(f"Preview: {url} (unpublished)")
    return

if __name__ == "__main__":
    app()