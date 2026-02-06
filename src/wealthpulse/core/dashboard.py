"""
Dashboard generator — renders the HTML portfolio report.
"""
import json
import os
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from wealthpulse.core.config import Config, DATA_DIR, OUTPUT_DIR
from wealthpulse.core.market_data import fetch_live_prices, fetch_market_movers, fetch_news


TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"


def _format_inr(value: float) -> str:
    """Format a number in Indian lakhs/crores style."""
    if abs(value) >= 1_00_00_000:
        return f"{value / 1_00_00_000:,.2f} Cr"
    elif abs(value) >= 1_00_000:
        return f"{value / 1_00_000:,.2f} L"
    else:
        return f"{value:,.0f}"


def _format_usd(value: float) -> str:
    """Format USD value."""
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:,.2f}M"
    elif abs(value) >= 1_000:
        return f"{value / 1_000:,.1f}K"
    else:
        return f"{value:,.2f}"


def _greeting() -> str:
    """Time-of-day greeting."""
    hour = datetime.now().hour
    if hour < 12:
        return "Good Morning ☀️"
    elif hour < 17:
        return "Good Afternoon 🌤️"
    else:
        return "Good Evening 🌙"


def generate_dashboard(config: Config, portfolio_path: str | None = None, output_path: str | None = None) -> str:
    """
    Generate the full HTML dashboard from portfolio data + live prices.

    Args:
        config: WealthPulse Config object
        portfolio_path: Path to portfolio_data.json (default: config data dir)
        output_path: Where to save the HTML file (default: config output dir)

    Returns:
        Path to the generated HTML file
    """
    # --- Load portfolio data ---
    if portfolio_path is None:
        portfolio_path = os.path.join(str(DATA_DIR), "portfolio_data.json")

    if not os.path.exists(portfolio_path):
        raise FileNotFoundError(
            f"Portfolio data not found at {portfolio_path}\n"
            "Run 'wealthpulse parse' first to parse your statements."
        )

    with open(portfolio_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # --- Extract holdings ---
    stocks_raw = data.get("stocks", {})
    mfs_raw = data.get("mutual_funds", [])
    us_raw = data.get("us_holdings", [])
    nps_raw = data.get("nps_holdings", [])
    epfo_raw = data.get("epfo_holdings", [])
    verdicts = data.get("verdicts", {})
    yahoo_map = data.get("yahoo_symbol_map", {})
    non_equity = config.get("non_equity", {})

    # --- Fetch live prices ---
    symbols = list(stocks_raw.keys())
    stock_prices, index_data = fetch_live_prices(symbols, yahoo_map)

    # --- Build holdings list ---
    holdings = []
    total_invested = 0
    total_current = 0
    stocks_fetched = 0
    sector_map = {}

    for symbol, info in stocks_raw.items():
        qty = info.get("qty", 0)
        avg_price = info.get("avg_price", 0)
        invested = info.get("invested", qty * avg_price)
        sector = info.get("sector", "Unknown")
        broker = info.get("broker", "")

        # Live price or closing price fallback
        cmp = stock_prices.get(symbol, 0)
        if cmp > 0:
            stocks_fetched += 1
        elif info.get("closing_price", 0) > 0:
            cmp = info["closing_price"]

        current = qty * cmp if cmp > 0 else invested
        pnl = current - invested
        pnl_pct = (pnl / invested * 100) if invested > 0 else 0

        verdict = verdicts.get(symbol, "HOLD")

        holdings.append({
            "symbol": symbol,
            "qty": qty,
            "avg_price": avg_price,
            "cmp": cmp,
            "invested": invested,
            "current": current,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "verdict": verdict,
            "sector": sector,
            "broker": broker,
        })

        total_invested += invested
        total_current += current

        # Sector aggregation
        sector_map[sector] = sector_map.get(sector, 0) + current

    # Sort by current value descending
    holdings.sort(key=lambda h: h["current"], reverse=True)

    total_pnl = total_current - total_invested
    pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0

    # --- Mutual Funds ---
    mutual_funds = []
    mf_total_inv = 0
    mf_total_cur = 0
    mf_xirrs = []

    for mf in mfs_raw:
        invested = mf.get("invested", 0)
        current = mf.get("current", invested)
        xirr = mf.get("xirr", 0)
        category = mf.get("category", "")

        mutual_funds.append({
            "name": mf.get("name", "Unknown"),
            "category": category,
            "invested": invested,
            "current": current,
            "xirr": xirr,
        })
        mf_total_inv += invested
        mf_total_cur += current
        if xirr != 0:
            mf_xirrs.append(xirr)

    mutual_funds.sort(key=lambda m: m["current"], reverse=True)
    mf_xirr_avg = sum(mf_xirrs) / len(mf_xirrs) if mf_xirrs else 0

    # --- US Holdings ---
    us_value_total = sum(h.get("value_usd", 0) for h in us_raw)

    # --- NPS Holdings ---
    nps_total = sum(h.get("current_value", 0) for h in nps_raw)
    nps_contribution = sum(h.get("contribution_total", 0) for h in nps_raw)

    # --- EPFO Holdings ---
    epfo_total = sum(h.get("total_balance", 0) for h in epfo_raw)
    epfo_interest = sum(h.get("interest_earned", 0) for h in epfo_raw)

    # --- Net Worth ---
    non_equity_total = sum(float(v) for v in non_equity.values()) if non_equity else 0
    net_worth = total_current + mf_total_cur + non_equity_total + nps_total + epfo_total
    # Add US holdings converted to INR (rough 83 rate, configurable)
    usd_inr_rate = index_data.get("USD/INR", {}).get("price", 83) if index_data else 83
    net_worth += us_value_total * usd_inr_rate

    # --- FIRE ---
    fire_cfg = config.fire
    fire_target = fire_cfg.get("target_corpus", 0)
    fire_target_age = fire_cfg.get("target_age", 0)
    current_age = fire_cfg.get("current_age", 0)
    fire_pct = (net_worth / fire_target * 100) if fire_target > 0 else 0
    years_to_fire = max(0, fire_target_age - current_age) if fire_target_age > 0 else 0

    # --- Asset allocation ---
    asset_labels = []
    asset_values = []
    if total_current > 0:
        asset_labels.append("Indian Equity")
        asset_values.append(round(total_current))
    if mf_total_cur > 0:
        asset_labels.append("Mutual Funds")
        asset_values.append(round(mf_total_cur))
    if us_value_total > 0:
        asset_labels.append("US Equity")
        asset_values.append(round(us_value_total * usd_inr_rate))
    if nps_total > 0:
        asset_labels.append("NPS")
        asset_values.append(round(nps_total))
    if epfo_total > 0:
        asset_labels.append("EPF")
        asset_values.append(round(epfo_total))
    for label, val in (non_equity or {}).items():
        if float(val) > 0:
            asset_labels.append(label)
            asset_values.append(round(float(val)))

    # --- Sector allocation ---
    sorted_sectors = sorted(sector_map.items(), key=lambda x: x[1], reverse=True)
    # Show top 8, collapse rest into "Others"
    sector_labels = []
    sector_values = []
    other_total = 0
    for i, (sec, val) in enumerate(sorted_sectors):
        if i < 8:
            sector_labels.append(sec)
            sector_values.append(round(val))
        else:
            other_total += val
    if other_total > 0:
        sector_labels.append("Others")
        sector_values.append(round(other_total))

    # --- Market Movers ---
    try:
        movers = fetch_market_movers(top_n=5)
        top_gainers = [m for m in movers if m.get("change_pct", 0) > 0][:5]
        top_losers = [m for m in movers if m.get("change_pct", 0) < 0][-5:]
        top_losers.reverse()
    except Exception:
        top_gainers, top_losers = [], []

    # --- News ---
    news_feeds = config.get("news_feeds", {})
    try:
        news = fetch_news(news_feeds, max_per_feed=5) if news_feeds else {}
    except Exception:
        news = {}

    # --- Index data wrapper ---
    class IndexItem:
        def __init__(self, d):
            self.price = d.get("price", 0)
            self.change = d.get("change", 0)
            self.change_pct = d.get("change_pct", 0)

    index_wrapped = {k: IndexItem(v) for k, v in (index_data or {}).items()}

    # --- Currency symbol ---
    currency = "₹"

    # --- Build template context ---
    context = {
        "theme": config.get("dashboard.theme", "dark"),
        "profile_name": config.get("profile.name", "My Portfolio"),
        "generated_date": datetime.now().strftime("%d %b %Y"),
        "generated_datetime": datetime.now().strftime("%d %b %Y, %I:%M %p"),
        "greeting": _greeting(),
        "currency": currency,

        # KPIs
        "net_worth_display": _format_inr(net_worth),
        "net_worth_raw": net_worth,
        "total_pnl": total_pnl,
        "pnl_display": _format_inr(abs(total_pnl)),
        "pnl_pct": pnl_pct,
        "equity_display": _format_inr(total_current),
        "mf_display": _format_inr(mf_total_cur),
        "mf_xirr_avg": mf_xirr_avg,
        "holdings_count": len(holdings),
        "mf_count": len(mutual_funds),
        "stocks_fetched": stocks_fetched,

        # FIRE
        "fire_target": fire_target,
        "fire_target_display": _format_inr(fire_target) if fire_target else "",
        "fire_target_age": fire_target_age,
        "fire_pct": fire_pct,
        "years_to_fire": years_to_fire,

        # US
        "us_value_display": _format_usd(us_value_total) if us_value_total > 0 else "",
        "us_count": len(us_raw),

        # NPS
        "nps_holdings": nps_raw,
        "nps_total": nps_total,
        "nps_total_display": _format_inr(nps_total) if nps_total > 0 else "",
        "nps_contribution": nps_contribution,

        # EPFO
        "epfo_holdings": epfo_raw,
        "epfo_total": epfo_total,
        "epfo_total_display": _format_inr(epfo_total) if epfo_total > 0 else "",
        "epfo_interest": epfo_interest,

        # Charts
        "asset_labels": asset_labels,
        "asset_values": asset_values,
        "sector_labels": sector_labels,
        "sector_values": sector_values,

        # Tables
        "holdings": holdings,
        "mutual_funds": mutual_funds,
        "mf_total_inv": mf_total_inv,
        "mf_total_cur": mf_total_cur,

        # Market
        "index_data": index_wrapped,
        "top_gainers": top_gainers,
        "top_losers": top_losers,

        # News
        "news": news,

        # Email config (for modal)
        "email_configured": bool(config.email.get("enabled", False) and config.email.get("sender_email", "") or config.email.get("sender", "")),
        "email_recipient": config.email.get("recipient_email", "") or config.email.get("sender_email", "") or config.email.get("sender", "") or (config.email.get("recipients", [""])[0] if isinstance(config.email.get("recipients"), list) else ""),
    }

    # --- Render template ---
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=False)
    template = env.get_template("dashboard.html")
    html = template.render(**context)

    # --- Save ---
    if output_path is None:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = os.path.join(str(OUTPUT_DIR), f"WealthPulse_Dashboard_{datetime.now().strftime('%Y%m%d')}.html")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    return output_path
