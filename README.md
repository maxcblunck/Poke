# Pokemon Value Finder
This is a project where I will be attempting to build my first python model ever using Claude Code to find over and under valued Pokemon Cards according to TCGPlayer market prices and EBay last solds. 
## 
For each card:
  1. Collect last 10-20 eBay sold prices
  2. Calculate the average sold price
  3. Calculate the median sold price (ignores outliers)
  4. Look at the trend — is it selling for more or less than 30 days ago?
  5. Flag it as:
     - UNDERVALUED → recent sales average is dropping but card is rare/popular
     - OVERVALUED  → recent sales spiking above historical average
     - FAIR VALUE  → prices are stable

