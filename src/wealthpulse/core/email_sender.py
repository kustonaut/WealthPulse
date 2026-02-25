"""
Email sender — sends the daily portfolio brief via SMTP.
"""
import json
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from wealthpulse.core.config import Config, DATA_DIR
from wealthpulse.core.market_data import fetch_live_prices, fetch_market_movers, fetch_news


TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"


def _format_inr(value: float) -> str:
    """Format in Indian style."""
    if abs(value) >= 1_00_00_000:
        return f"{value / 1_00_00_000:,.2f} Cr"
    elif abs(value) >= 1_00_000:
        return f"{value / 1_00_000:,.2f} L"
    else:
        return f"{value:,.0f}"


def _greeting() -> str:
    hour = datetime.now().hour
    if hour < 12:
        return "Good Morning ☀️"
    elif hour < 17:
        return "Good Afternoon 🌤️"
    else:
        return "Good Evening 🌙"


def send_daily_brief(config: Config, portfolio_path: str | None = None) -> bool:
    """
    Build and send the daily email brief.

    Supports environment variable overrides for CI/CD:
        GMAIL_ADDRESS      → sender email
        GMAIL_APP_PASSWORD → app password
        GMAIL_RECIPIENTS   → comma-separated recipient list

    Args:
        config: WealthPulse Config object
        portfolio_path: Path to portfolio_data.json

    Returns:
        True if email sent successfully
    """
    email_cfg = config.email

    # Environment variable overrides (GitHub Actions)
    env_sender = os.environ.get("GMAIL_ADDRESS")
    env_password = os.environ.get("GMAIL_APP_PASSWORD")
    env_recipients = os.environ.get("GMAIL_RECIPIENTS")

    sender = env_sender or email_cfg.get("sender_email", "") or email_cfg.get("sender", "")
    password = env_password or email_cfg.get("app_password", "")
    if env_recipients:
        recipients = [r.strip() for r in env_recipients.split(",") if r.strip()]
    else:
        recipients = email_cfg.get("recipients", [])
        if isinstance(recipients, str):
            recipients = [recipients]
    smtp_server = email_cfg.get("smtp_server", "smtp.gmail.com")
    smtp_port = email_cfg.get("smtp_port", 587)

    # Check if running in CI mode (env vars provided) — override enabled check
    ci_mode = bool(env_sender and env_password and env_recipients)
    if not ci_mode and not email_cfg.get("enabled", False):
        print("Email is disabled in config. Set email.enabled: true")
        return False

    if not all([sender, password, recipients]):
        print("Email config incomplete. Need sender, app_password, and recipients.")
        return False

    # Load portfolio data
    if portfolio_path is None:
        portfolio_path = os.path.join(str(DATA_DIR), "portfolio_data.json")

    if not os.path.exists(portfolio_path):
        print(f"Portfolio data not found: {portfolio_path}")
        return False

    with open(portfolio_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    stocks_raw = data.get("stocks", {})
    mfs_raw = data.get("mutual_funds", [])
    yahoo_map = data.get("yahoo_symbol_map", {})

    # Fetch live prices
    symbols = list(stocks_raw.keys())
    stock_prices, index_data = fetch_live_prices(symbols, yahoo_map)

    # Calculate portfolio values
    total_current = 0
    day_pnl = 0
    portfolio_movers = []

    for symbol, info in stocks_raw.items():
        qty = info.get("qty", 0)
        avg_price = info.get("avg_price", 0)
        invested = info.get("invested", qty * avg_price)

        cmp = stock_prices.get(symbol, 0)
        if cmp <= 0:
            cmp = info.get("closing_price", avg_price)

        current = qty * cmp
        total_current += current

        # Estimate day's change (using prev close from yfinance if available)
        prev_close = info.get("closing_price", cmp)
        stock_day_pnl = qty * (cmp - prev_close) if prev_close > 0 else 0
        day_pnl += stock_day_pnl

        change_pct = ((cmp - prev_close) / prev_close * 100) if prev_close > 0 else 0

        portfolio_movers.append({
            "symbol": symbol,
            "price": cmp,
            "change_pct": change_pct,
            "day_pnl": stock_day_pnl,
        })

    # Sort movers by absolute change
    portfolio_movers.sort(key=lambda x: abs(x["day_pnl"]), reverse=True)
    portfolio_movers = portfolio_movers[:10]  # Top 10

    # MF summary
    mf_total_cur = sum(mf.get("current", 0) for mf in mfs_raw)
    mf_total_inv = sum(mf.get("invested", 0) for mf in mfs_raw)
    mf_pnl = mf_total_cur - mf_total_inv

    # Market movers
    try:
        movers = fetch_market_movers(top_n=5)
        top_gainers = [m for m in movers if m.get("change_pct", 0) > 0][:5]
        top_losers = sorted([m for m in movers if m.get("change_pct", 0) < 0],
                            key=lambda x: x["change_pct"])[:5]
    except Exception:
        top_gainers, top_losers = [], []

    # News
    news_feeds = config.get("news_feeds", {})
    try:
        news = fetch_news(news_feeds, max_per_feed=3) if news_feeds else {}
    except Exception:
        news = {}

    # Build context
    class IndexItem:
        def __init__(self, d):
            self.price = d.get("price", 0)
            self.change = d.get("change", 0)
            self.change_pct = d.get("change_pct", 0)

    # Only show key indices in email (keep it compact)
    key_indices = ["NIFTY 50", "SENSEX", "NIFTY Bank", "Gold", "USD/INR"]
    filtered_index = {k: IndexItem(v) for k, v in (index_data or {}).items() if k in key_indices}

    currency = "₹"
    context = {
        "subject": f"WealthPulse Brief — {datetime.now().strftime('%d %b %Y')}",
        "date_display": datetime.now().strftime("%A, %d %b %Y"),
        "greeting": _greeting(),
        "currency": currency,
        "equity_display": _format_inr(total_current),
        "day_pnl": day_pnl,
        "day_pnl_display": _format_inr(abs(day_pnl)),
        "portfolio_movers": portfolio_movers,
        "mf_display": _format_inr(mf_total_cur) if mf_total_cur > 0 else "",
        "mf_pnl": mf_pnl,
        "mf_pnl_display": _format_inr(abs(mf_pnl)),
        "index_data": filtered_index,
        "top_gainers": top_gainers,
        "top_losers": top_losers,
        "news": news,
    }

    # Render template
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=False)
    template = env.get_template("email_brief.html")
    html_body = template.render(**context)

    subject = context["subject"]

    # Send email
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = ", ".join(recipients)
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender, password)
            server.sendmail(sender, recipients, msg.as_string())

        print(f"✅ Daily brief sent to {', '.join(recipients)}")
        return True

    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        return False
