# E-com Brand Scraper

Finds **e-commerce brands** in a niche you choose and exports a CSV with, for each brand:

| Column group | What you get |
|---|---|
| Basics | Brand name, domain, website, platform (Shopify, WooCommerce, …) |
| What they're about | Summary from their About / Our Story page (or written by Claude if enabled) |
| Founder | Founder name + best email, with a confidence level (`verified`, `high`, `medium`, `low`) and the page it came from, plus other emails found |
| Location & age | Where the brand says it's based, whether that matches the location you picked, and brand age (with how it was determined) |
| Store data | Product count, price range, average price (from Shopify's public catalog) |
| Socials | Instagram, TikTok, Facebook, YouTube, Pinterest, LinkedIn, X |
| Marketing | Detected marketing stack (pixels, Klaviyo, SMS, reviews, loyalty, subscriptions, BNPL, chat…) and a 0–100 marketing score |
| **How they can improve** | Separate **website**, **marketing** and **brand/company** improvement ideas |

You pick **how many brands**, the **niche** (16 presets or your own), optional keywords, a
**location** (country, state/province and city, as specific as you like) and **brand age**.

```
ecom-scraper/
├── backend/    Python: scraper + FastAPI server + interactive CLI
└── frontend/   Next.js interface
```

## Easiest way: double-click

1. Install [Python](https://www.python.org/downloads/) (on Windows, tick **"Add Python to PATH"**)
   and [Node.js](https://nodejs.org/) (LTS). You only do this once.
2. Double-click **`Start (Mac).command`** or **`Start (Windows).bat`** in this folder.
   - The first time, it installs everything (a few minutes).
   - Your browser opens the scraper at http://localhost:3000 by itself.
3. Keep the black window open while you use it. Close it to stop.

On a Mac, if it says the file "can't be opened", right-click it, choose **Open**, then click **Open** again.

## Manual start

You need Python 3.10+ and Node.js 18.18+.

**1. Backend (terminal 1)**

```bash
cd ecom-scraper/backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # optional: add API keys (see below)
python server.py                   # API on http://127.0.0.1:8000
```

**2. Frontend (terminal 2)**

```bash
cd ecom-scraper/frontend
npm install
npm run dev                        # open http://localhost:3000
```

Fill in the form and click **Find N brands**. Results show up live, and **Download CSV**
works during the run (partial file) and after it finishes. Finished CSVs are also saved
in `backend/output/`.

**Prefer the terminal?** `python cli.py` asks the same questions and writes the CSV.

## API keys (all optional, but they make a big difference)

Put them in `backend/.env`:

| Key | What it adds | Without it |
|---|---|---|
| `BRAVE_API_KEY` ([free tier](https://brave.com/search/api/)) or `SERPAPI_KEY` | Reliable brand discovery | Falls back to DuckDuckGo's HTML results, fine for small runs but can be rate-limited |
| `HUNTER_API_KEY` ([hunter.io](https://hunter.io/api)) | Verified founder/CEO emails | Uses only emails published on the brand's own site |
| `ANTHROPIC_API_KEY` | Claude writes the "what they do" summary and tailored improvement ideas, and double-checks that each site is a real brand in your niche | Rule-based summary + ideas (still specific to what's missing on each site) |

Claude requests use `claude-opus-5-5` at low effort (change with `ANTHROPIC_MODEL`) with
server-side refusal fallback turned on.

## How it works

1. **Discover**: runs niche searches for brand stores, plus "best *niche* brands" roundup
   articles, whose outbound links are collected. Marketplaces (Amazon, Etsy…), social networks
   and media sites are skipped. Any URLs you paste under *Advanced* are checked first.
2. **Qualify**: fetches the homepage and keeps only real online stores (cart, product pages,
   e-commerce platform signals) that match the niche.
3. **Scrape**: About/Our Story and Contact pages for the story, founder name and emails
   (including `name [at] brand [dot] com` style), plus socials and marketing tools.
4. **Enrich** from public sources:
   - **Age**: "founded/est. 20XX" on the site → oldest product listing → domain registration date (RDAP).
   - **Catalog**: Shopify's public `/products.json` for product count and prices.
5. **Filter** by location and age. The location is read from the site (address, "based in…",
   "made in…") and checked against your choice. Brands that don't confirm it are kept and
   marked "not confirmed", unless you tick *Only keep brands whose website confirms they're
   based there*. Brands of unknown age are kept unless you tick *Strict age filter*.
6. **Analyse**: scores marketing maturity and writes improvement ideas.

### About the numbers

- **Location** is only what the brand states on its own site. Many small brands don't say
  where they're based, so "not confirmed" often just means "not stated".
- **Email confidence**: `verified` = Hunter.io; `high` = matches the founder's name or is
  founder@/ceo@; `medium` = a person's address on the brand domain; `low` = a general inbox like hello@ or info@.

## Responsible use

The scraper reads only public pages, follows `robots.txt`, spaces out requests to each site and
identifies itself with its own user-agent. It never guesses or generates email addresses.
If you use the results for outreach, follow CAN-SPAM, GDPR/PECR and CASL: say who you are,
include an opt-out, and honour unsubscribes.

## Tests

```bash
cd backend && pytest        # parsing, filters, CSV and full pipeline runs on mocked HTTP
cd frontend && npm run build
```
