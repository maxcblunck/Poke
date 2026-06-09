# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the web app (primary entry point)
streamlit run app.py

# Test PokéWallet API integration directly
python src/pokewallet_test.py

# Legacy CLI interface
python src/main.py
```

## Architecture

**Poke** is a Streamlit web app for Pokemon card valuation and analysis. The entry point is `app.py`; pages live in `pages/` and are auto-registered by Streamlit (1_Popularity, 2_Search, 3_Game).

### Core modules (`src/`)

| Module | Responsibility |
|---|---|
| `card_db.py` | Loads card JSON files from `data/cards/en/` into a `CardDatabase` instance; search and filter |
| `scraper.py` | API clients for PokéWallet, PokeTrace, and TCGPlayer; handles caching of sets/tokens |
| `card_valuator.py` | Simulated pricing engine — base prices by rarity + weighted multipliers (popularity 30%, nostalgia 15%, subtype 10%, age 8%, ability 5%, etc.) |
| `analyzer.py` | Price analysis: era classification, PSA grade multipliers, volatility/trend scoring, undervalued/overvalued classification |
| `pokemon_popularity.py` | Static popularity scores by Pokemon for use in valuator multipliers |
| `ui_helpers.py` | All Streamlit UI components, custom CSS (Pokemon dark theme with gold `#FFDE00` accents), session state caching |
| `reporter.py` | CSV export to `data/prices/results.csv`, buy/sell recommendation formatting |

### Data flow

`CardDatabase` → `Scraper` (live prices) or `CardValuator` (simulated prices) → `Analyzer` (scoring) → `Reporter` (output) / `ui_helpers` (display)

## Git workflow

After completing any task, always run:

```bash
git add .
git commit -m "<concise description of what changed>"
git push
```

### Configuration

- API keys go in `.env`: `POKEWALLET_API_KEY`, `POKETRACE_API_KEY`, `TCGPLAYER_PUBLIC_KEY`, `TCGPLAYER_PRIVATE_KEY`
- Streamlit theme is in `.streamlit/config.toml`
- `data/prices/results.csv` and `.env` are gitignored
