"""
Market data fetcher — live stock prices, indices, and news via yfinance + RSS.
"""

from datetime import datetime
from typing import Optional

# Major Indian indices and commodities
INDEX_TICKERS = {
    'NIFTY 50': '^NSEI',
    'SENSEX': '^BSESN',
    'NIFTY Bank': '^NSEBANK',
    'NIFTY IT': '^CNXIT',
    'NIFTY Midcap': 'NIFTY_MIDCAP_100.NS',
    'India VIX': '^INDIAVIX',
    'Gold (INR/10g)': 'GC=F',
    'Silver (USD)': 'SI=F',
    'Crude Oil': 'CL=F',
    'USD/INR': 'USDINR=X',
    'US 10Y Yield': '^TNX',
    'S&P 500': '^GSPC',
    'NASDAQ': '^IXIC',
    'Nifty Smallcap': '^CNXSMALLCAP',
}

# NIFTY 50 constituents for market movers
NIFTY50_TICKERS = [
    'RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'ICICIBANK.NS',
    'HINDUNILVR.NS', 'ITC.NS', 'SBIN.NS', 'BHARTIARTL.NS', 'KOTAKBANK.NS',
    'LT.NS', 'AXISBANK.NS', 'BAJFINANCE.NS', 'HCLTECH.NS', 'ASIANPAINT.NS',
    'MARUTI.NS', 'SUNPHARMA.NS', 'TITAN.NS', 'WIPRO.NS', 'ULTRACEMCO.NS',
    'BAJAJFINSV.NS', 'NESTLEIND.NS', 'TATAMOTORS.NS', 'NTPC.NS', 'POWERGRID.NS',
    'M&M.NS', 'TATASTEEL.NS', 'TECHM.NS', 'ONGC.NS', 'HDFCLIFE.NS',
    'COALINDIA.NS', 'ADANIENT.NS', 'ADANIPORTS.NS', 'DRREDDY.NS', 'CIPLA.NS',
    'DIVISLAB.NS', 'BRITANNIA.NS', 'JSWSTEEL.NS', 'SBILIFE.NS', 'TATACONSUM.NS',
    'GRASIM.NS', 'INDUSINDBK.NS', 'BAJAJ-AUTO.NS', 'EICHERMOT.NS', 'APOLLOHOSP.NS',
    'HEROMOTOCO.NS', 'BPCL.NS', 'SHRIRAMFIN.NS', 'HINDALCO.NS', 'TRENT.NS',
]


def fetch_live_prices(symbols: list[str], yahoo_map: dict = None) -> tuple[dict, dict]:
    """
    Fetch live prices for portfolio stocks and market indices.

    Args:
        symbols: List of stock symbols (e.g., ['HDFCBANK', 'TCS'])
        yahoo_map: Optional mapping of symbol → Yahoo Finance ticker

    Returns:
        (stock_prices, index_data) — both are {name: price} dicts
    """
    import yfinance as yf

    yahoo_map = yahoo_map or {}
    stock_prices = {}
    index_data = {}

    # Fetch stock prices
    if symbols:
        tickers = []
        sym_lookup = {}
        for sym in symbols:
            yf_ticker = yahoo_map.get(sym, f"{sym}.NS")
            tickers.append(yf_ticker)
            sym_lookup[yf_ticker] = sym

        try:
            data = yf.download(tickers, period='2d', progress=False, threads=True)
            if 'Close' in data.columns or len(tickers) == 1:
                close = data['Close']
                if len(tickers) == 1:
                    # Single ticker returns a Series
                    price = close.dropna().iloc[-1] if len(close.dropna()) > 0 else 0
                    stock_prices[symbols[0]] = round(float(price), 2)
                else:
                    for yf_t, sym in sym_lookup.items():
                        if yf_t in close.columns:
                            vals = close[yf_t].dropna()
                            if len(vals) > 0:
                                stock_prices[sym] = round(float(vals.iloc[-1]), 2)
        except Exception:
            pass

    # Fetch index/commodity data
    idx_tickers = list(INDEX_TICKERS.values())
    try:
        idx_data = yf.download(idx_tickers, period='5d', progress=False, threads=True)
        if 'Close' in idx_data.columns:
            close = idx_data['Close']
            for name, ticker in INDEX_TICKERS.items():
                if ticker in close.columns:
                    vals = close[ticker].dropna()
                    if len(vals) >= 2:
                        cur = float(vals.iloc[-1])
                        prev = float(vals.iloc[-2])
                        chg = cur - prev
                        chg_pct = (chg / prev * 100) if prev else 0
                        index_data[name] = {
                            'price': round(cur, 2),
                            'change': round(chg, 2),
                            'change_pct': round(chg_pct, 2),
                        }
                    elif len(vals) == 1:
                        index_data[name] = {
                            'price': round(float(vals.iloc[0]), 2),
                            'change': 0,
                            'change_pct': 0,
                        }
    except Exception:
        pass

    return stock_prices, index_data


def fetch_market_movers(top_n: int = 5) -> list[dict]:
    """
    Fetch NIFTY 50 stocks and identify top gainers/losers.

    Returns:
        List of dicts with 'symbol', 'price', 'change', 'change_pct'
    """
    import yfinance as yf

    movers = []
    try:
        data = yf.download(NIFTY50_TICKERS, period='5d', progress=False, threads=True)
        if 'Close' in data.columns:
            close = data['Close']
            for ticker in NIFTY50_TICKERS:
                if ticker in close.columns:
                    vals = close[ticker].dropna()
                    if len(vals) >= 2:
                        cur = float(vals.iloc[-1])
                        prev = float(vals.iloc[-2])
                        chg = cur - prev
                        chg_pct = (chg / prev * 100) if prev else 0
                        movers.append({
                            'symbol': ticker.replace('.NS', ''),
                            'price': round(cur, 2),
                            'change': round(chg, 2),
                            'change_pct': round(chg_pct, 2),
                        })
    except Exception:
        pass

    return movers


def fetch_news(feeds: dict, max_per_feed: int = 3) -> dict:
    """
    Fetch market news from RSS feeds.

    Args:
        feeds: Dict of {category: rss_url}
        max_per_feed: Max headlines per feed

    Returns:
        Dict of {category: [{'title': ..., 'link': ..., 'date': ...}]}
    """
    import feedparser

    news = {}
    for category, url in feeds.items():
        try:
            feed = feedparser.parse(url)
            items = []
            for entry in feed.entries[:max_per_feed]:
                items.append({
                    'title': entry.get('title', ''),
                    'link': entry.get('link', ''),
                    'date': entry.get('published', ''),
                })
            if items:
                news[category] = items
        except Exception:
            continue

    return news
