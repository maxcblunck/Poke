# PokéValue

A Streamlit web app for Pokémon card valuation and investment analysis, with a built-in Frogger-style game.

## Features

### Card Search & Valuation
- Search across a local database of English Pokémon cards
- Fetch live TCGPlayer prices via the **PokeWallet** and **PokeTrace** APIs
- **Composite score** (−100 to +100) built from 10 weighted signals:
  - Price vs. historical average, trend, momentum, volatility
  - Popularity, scarcity, pull odds, bid-ask spread, sale velocity, rarity baseline
- Buy / Hold / Sell recommendation with color-coded badge
- Price history chart (last 10–20 sales), market snapshot table (floor / mid / market / high)
- Variant switching for alternate printings (1st edition, shadowless, IRs, etc.)
- PSA grade multiplier projections for gradeable cards
- Falls back to simulated pricing if no live data is available

### Popularity Rankings
- Top 20 Pokémon by fan popularity score across all 1025 species
- Card images fetched from PokeAPI; color-coded progress bars
- Database stats: total cards, distinct sets, rare card count, tracked species

### PokéCross (mini-game)
- Frogger-style canvas game embedded in the Streamlit page
- Choose from 4 characters: Pikachu, Charmander, Bulbasaur, Squirtle
- Dodge cars (Snorlax / Rapidash / Doduo), ride Lapras logs, survive Rayquaza fly-bys
- Score = tiles advanced; difficulty scales with distance
- Best score persisted in browser `localStorage`
- Arrow keys / WASD on desktop; on-screen D-pad on mobile

## Running the app

```bash
pip install -r requirements.txt
streamlit run app.py
```

Copy `.env.example` → `.env` and add your API keys:

```
POKEWALLET_API_KEY=...
POKETRACE_API_KEY=...
TCGPLAYER_PUBLIC_KEY=...
TCGPLAYER_PRIVATE_KEY=...
```

## Architecture

```
app.py                  # Streamlit entry point, hero banner, nav
pages/
  1_Popularity.py       # Popularity rankings page
  2_Search.py           # Card search + live valuation page
  3_Game.py             # PokéCross game embed
src/
  card_db.py            # Loads card JSON from data/cards/en/; search & filter
  scraper.py            # PokeWallet, PokeTrace, TCGPlayer API clients + disk caching
  analyzer.py           # 10-factor composite scoring engine; era/rarity/grade logic
  card_valuator.py      # Simulated pricing fallback (rarity base + multipliers)
  pokemon_popularity.py # Hardcoded popularity scores for all 1025 species
  ui_helpers.py         # CSS theme, Streamlit components, badges, signal chips
  reporter.py           # CSV export, buy/sell formatting
game.html               # Pure-JS canvas game (9×11 tile grid, smooth easing, mobile D-pad)
data/
  cards/en/             # Card JSON files (one per set)
  prices/results.csv    # Exported analysis results (gitignored)
```

**Data flow:** `CardDatabase` → `Scraper` (live) or `CardValuator` (simulated) → `Analyzer` (scoring) → `ui_helpers` (display) / `Reporter` (export)

## Tech stack

- [Streamlit](https://streamlit.io) — web framework
- [Plotly](https://plotly.com) — composite score gauge + price history charts
- [PokeWallet API](https://pokewallet.com) — live TCGPlayer NM prices
- [PokeTrace API](https://poketrace.com) — secondary market sale history
- [PokeAPI](https://pokeapi.co) — Pokémon sprites and artwork
- Pure JavaScript canvas game (no framework)
