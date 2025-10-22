LinkMint — Zero-DB microstore (FastAPI + Stripe + Printful)

Setup
1) Copy .env.example to .env and fill keys.
2) docker compose up --build -d
3) Open http://SERVER:8000/healthz

CLI
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python cli/linkmint_cli.py --help

Import Flow
1) linkmint stripe:set-key sk_test_xxx
2) linkmint printful:set-key pft_xxx
3) linkmint printful:import <printful_product_id> --price 1999 --currency EUR --theme default
4) linkmint product:publish <slug>
5) Open URL: BASE_URL/p/<slug>

Stripe Webhook
Set endpoint to: https://SERVER/api/stripe/webhook with STRIPE_WEBHOOK_SECRET

Email Provider
Set EMAIL_PROVIDER and EMAIL_API_KEY in .env to enable transactional emails.

Themes
Edit templates/themes/default or add new theme and set Product.metadata.theme.
