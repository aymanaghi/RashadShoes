# Rashad Shoes

Online shop and stock system for **Rashad Shoes**, a shoe shop in Tripoli, Lebanon
([@rashad_shoes_tripoli](https://www.instagram.com/rashad_shoes_tripoli/)).

The goal is to replace the paper stock notebook with a real inventory, then put
that inventory online so customers can pick a size and order on WhatsApp. Later
they will also be able to pay through checkout with cash on delivery, Whish or OMT.

## What works now

| Part | What it does |
|---|---|
| **Stock per size** | Every shoe model has variants (colour + EU size), each with its own pair count. |
| **Stock log** | Every change (first count, new delivery, sale, return, correction) is recorded with who did it and why. This is the digital notebook. Stock can't go below zero. |
| **Shop panel** (`/panel/`) | Phone-friendly admin. Add shoes, add a whole size run at once (`Black` + `40-44` + `2 pairs each`), edit counts (edits are logged), filter sold out / running low, one click for "sold 1 pair" or "received 1 pair". |
| **Importer** | Load the notebook from a CSV. Re-running it updates prices and counts without duplicating anything. |
| **Storefront** | Catalog with Men / Women / Kids, type, brand, search (including by code) and a size rail that only shows sizes on the shelf. The product page lets you pick colour and size, then **Order on WhatsApp** opens a message already filled in with the shoe, colour, size, price, code and link. |
| **Orders (back end)** | Orders, delivery zones, Cash / Whish / OMT payment states, "payment received", "out for delivery" and "cancel + put back in stock" actions. The website checkout that creates these orders comes next. |

## Run it locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python manage.py migrate
python manage.py seed_demo          # example shoes + delivery areas (not real stock)
python manage.py createsuperuser    # login for /panel/
SHOP_WHATSAPP=9613123456 python manage.py runserver
```

Open http://localhost:8000 for the shop and http://localhost:8000/panel/ for the panel.

## Load the notebook

1. Copy `sample_data/inventory_template.csv` and fill one row per **shoe model + colour**:

   | brand | model | category | gender | color | sizes | pairs | price |
   |---|---|---|---|---|---|---|---|
   | Nike | Air Force 1 | Sneakers | men | White | 40-44 | 2 | 85 |

   - `sizes`: a range `40-44`, half sizes `36.5-38`, or a list `38, 39, 41`
   - `pairs`: how many pairs of **each** size
   - `gender`: men, women, kids or unisex (رجالي / نسائي / ولادي also work)
   - Optional: `compare_at_price` (old price, shows a Sale badge), `description`
   - If two colours of the same shoe have different prices, the first row sets the
     shoe's price and the other colour gets its own price automatically.

2. Check it first, then import:

   ```bash
   python manage.py import_inventory notebook.csv --dry-run
   python manage.py import_inventory notebook.csv
   ```

   If any row has a mistake, nothing is imported and every problem is listed with its row number.

## Run with Docker (Postgres)

```bash
cp .env.example .env   # fill in the secret key, passwords and WhatsApp number
docker compose up -d --build
docker compose exec web python manage.py createsuperuser
```

Product photos are stored in the `media` volume.

## Free preview on Render

`render.yaml` sets up the site and a Postgres database in one go.

1. Sign in at [render.com](https://render.com) with GitHub (no card needed).
2. **New → Blueprint**, pick this repo, click **Apply**.
3. When asked, fill in `DJANGO_ADMIN_PASSWORD` (panel login, username `rashad`)
   and `SHOP_WHATSAPP` (digits only, e.g. `9613123456`).
4. Wait for the first deploy, then open the `…onrender.com` link. The panel is at `/panel/`.

Preview limits on the free plan: the site sleeps after 15 minutes without visitors
(the first visit then takes about a minute), the free database expires after 30 days, and
photos uploaded in the panel disappear when the site restarts. That's fine for showing
it around, not for real stock. `SEED_DEMO=true` loads the example shoes; set it to
`false` once real stock goes in.

## Tests

```bash
pytest
```

The suite covers the stock rules (no negative stock, every change logged), placing and
cancelling orders, Whish/OMT payment states, the importer (re-import, dry run,
bad files), storefront filters, the WhatsApp message, and the panel's logged stock edits.

## Roadmap

1. ✅ Data model, stock log, shop panel, CSV importer
2. ✅ Storefront catalog + WhatsApp ordering
3. ⏳ Digitise the real notebook + product photo day
4. ⏳ Cart and checkout with delivery areas
5. ⏳ Payments: cash on delivery, Whish, OMT (manual confirmation first)
6. ⏳ n8n alerts for new orders and low stock, weekly sales summary
7. ⏳ Arabic version of the storefront

## Project layout

```
catalog/      shoes, sizes, stock log, importer, storefront views
  stock.py    the only place stock changes
  importer.py notebook CSV import
orders/       delivery zones, orders, payment states
  services.py place / cancel / confirm payment
templates/    storefront HTML
static/       CSS and images
tests/        pytest suite
```
