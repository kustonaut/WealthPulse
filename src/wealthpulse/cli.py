"""
WealthPulse CLI — your personal finance command center.

Usage:
    wealthpulse setup       Interactive setup wizard
    wealthpulse parse       Parse broker statements → portfolio JSON
    wealthpulse dashboard   Generate HTML portfolio dashboard
    wealthpulse email       Send daily portfolio brief email
    wealthpulse demo        Run with sample data to see it in action
"""
import argparse
import json
import os
import shutil
import sys
import webbrowser
from datetime import datetime
from pathlib import Path

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich import print as rprint
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from wealthpulse import __version__
from wealthpulse.core.config import Config, ROOT, CONFIG_DIR, DATA_DIR

console = Console() if RICH_AVAILABLE else None


def _print(msg: str, style: str = ""):
    """Print with rich if available, otherwise plain."""
    if RICH_AVAILABLE:
        console.print(msg, style=style)
    else:
        print(msg)


def _banner():
    """Show the WealthPulse banner."""
    banner = """
╔══════════════════════════════════════════════════════╗
║                                                      ║
║   💰 WealthPulse v{version}                            ║
║   Your Open-Source Portfolio Dashboard                ║
║                                                      ║
╚══════════════════════════════════════════════════════╝
    """.format(version=__version__)
    if RICH_AVAILABLE:
        console.print(Panel.fit(
            f"[bold cyan]💰 WealthPulse[/bold cyan] [dim]v{__version__}[/dim]\n"
            "[white]Your Open-Source Portfolio Dashboard[/white]",
            border_style="cyan",
        ))
    else:
        print(banner)


# ── SETUP WIZARD ─────────────────────────────────────────────

def cmd_setup(args):
    """Interactive setup wizard."""
    _banner()
    _print("\n🚀 Let's set up your WealthPulse!\n", style="bold")

    config_path = os.path.join(CONFIG_DIR, "config.yaml")
    example_path = os.path.join(CONFIG_DIR, "config.example.yaml")

    # Step 1: Create directory structure
    _print("📁 Step 1/5 — Creating directory structure...", style="bold yellow")
    Config.ensure_dirs()
    _print("   ✅ Created: config/, data/statements/, output/\n", style="green")

    # Step 2: Config file
    _print("📝 Step 2/5 — Configuration", style="bold yellow")
    if os.path.exists(config_path):
        _print(f"   Config already exists: {config_path}", style="dim")
        overwrite = input("   Overwrite? (y/N): ").strip().lower()
        if overwrite != "y":
            _print("   Keeping existing config.\n", style="dim")
        else:
            _create_config_interactive(config_path, example_path)
    else:
        _create_config_interactive(config_path, example_path)

    # Step 3: Broker setup
    _print("📊 Step 3/5 — Broker Statements", style="bold yellow")
    _print("   Place your broker statement files in:", style="")
    _print(f"   📂 {os.path.join(DATA_DIR, 'statements')}", style="cyan")
    _print("")
    _print("   Supported formats:", style="")
    _print("   • Groww:          Grow_*.xlsx or Groww_*.xlsx", style="dim")
    _print("   • Zerodha:        Zerodha_*.xlsx or kite_*.xlsx", style="dim")
    _print("   • Mutual Funds:   MutualFunds_*.xlsx or CAS_*.xlsx", style="dim")
    _print("   • Fidelity (US):  Fidelity_*.pdf", style="dim")
    _print("   • Morgan Stanley: MorganStanley_*.pdf or MSRS_*.pdf", style="dim")
    _print("")
    input("   Press Enter when you've placed your files (or skip for now)... ")
    _print("")

    # Step 4: Email setup (optional)
    _print("📧 Step 4/5 — Daily Email Brief (optional)", style="bold yellow")
    setup_email = input("   Set up daily email notifications? (y/N): ").strip().lower()
    if setup_email == "y":
        _setup_email(config_path)
    else:
        _print("   Skipped. You can set it up later in config/config.yaml\n", style="dim")

    # Step 5: Summary
    _print("✅ Step 5/5 — You're all set!\n", style="bold green")
    _print("   Next steps:", style="bold")
    _print("   1. wealthpulse parse       → Parse your statements", style="cyan")
    _print("   2. wealthpulse dashboard   → Generate your dashboard", style="cyan")
    _print("   3. wealthpulse email       → Send daily brief", style="cyan")
    _print("   4. wealthpulse demo        → Try with sample data first\n", style="cyan")


def _create_config_interactive(config_path: str, example_path: str):
    """Walk the user through creating a config file."""
    config = {}

    # Profile
    name = input("   Your name (for dashboard header): ").strip() or "My Portfolio"
    config["profile"] = {"name": name}

    # FIRE goals
    _print("\n   🔥 FIRE Planning (optional — press Enter to skip)", style="")
    target = input("   FIRE target corpus (e.g. 50000000): ").strip()
    if target:
        target_age = input("   Target retirement age (e.g. 45): ").strip() or "45"
        current_age = input("   Your current age: ").strip() or "30"
        monthly_sip = input("   Monthly SIP amount (e.g. 100000): ").strip() or "0"
        config["fire"] = {
            "target_corpus": int(target),
            "target_age": int(target_age),
            "current_age": int(current_age),
            "monthly_sip": int(monthly_sip),
            "expected_return": 12.0,
        }

    # Brokers
    _print("\n   📊 Which brokers do you use?", style="")
    brokers = {}
    for broker, default_name in [
        ("groww", "Groww"), ("zerodha", "Zerodha"),
        ("mutual_funds", "Mutual Funds (CAS)"),
        ("fidelity", "Fidelity (US)"), ("morgan_stanley", "Morgan Stanley (US)")
    ]:
        use = input(f"   Use {default_name}? (y/N): ").strip().lower()
        brokers[broker] = {"enabled": use == "y"}
    config["brokers"] = brokers

    # Dashboard preferences
    _print("\n   🎨 Dashboard", style="")
    theme = input("   Theme — dark or light? (dark): ").strip().lower() or "dark"
    config["dashboard"] = {"theme": theme}

    # Write config
    import yaml
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    _print(f"\n   ✅ Config saved: {config_path}\n", style="green")


def _setup_email(config_path: str):
    """Configure email settings."""
    import yaml

    _print("\n   For Gmail: Create an App Password at", style="")
    _print("   https://myaccount.google.com/apppasswords\n", style="cyan")

    sender = input("   Sender email: ").strip()
    password = input("   App password: ").strip()
    recipient = input("   Send to email: ").strip()

    if not all([sender, password, recipient]):
        _print("   ⚠️  Incomplete email config, skipping.\n", style="yellow")
        return

    # Load and update config
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            config = yaml.safe_load(f) or {}
    else:
        config = {}

    config["email"] = {
        "enabled": True,
        "sender": sender,
        "app_password": password,
        "recipients": [recipient],
        "smtp_server": "smtp.gmail.com",
        "smtp_port": 587,
    }

    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    _print("   ✅ Email configured!\n", style="green")


# ── PARSE ────────────────────────────────────────────────────

def cmd_parse(args):
    """Parse broker statements and build portfolio JSON."""
    _banner()
    _print("📊 Parsing broker statements...\n", style="bold")

    config = Config()
    from wealthpulse.core.portfolio import parse_all_statements, save_portfolio

    result = parse_all_statements(config)

    # Summary
    stocks = result.get("stocks", {})
    mfs = result.get("mutual_funds", [])
    us = result.get("us_holdings", [])

    total_inv = sum(s.get("invested", 0) for s in stocks.values())

    if RICH_AVAILABLE:
        table = Table(title="Parse Results")
        table.add_column("Category", style="cyan")
        table.add_column("Count", style="white", justify="right")
        table.add_column("Value", style="green", justify="right")
        table.add_row("Indian Stocks", str(len(stocks)), f"₹{total_inv:,.0f} invested")
        table.add_row("Mutual Funds", str(len(mfs)), f"₹{sum(m.get('current', 0) for m in mfs):,.0f} current")
        table.add_row("US Holdings", str(len(us)), f"${sum(h.get('value_usd', 0) for h in us):,.0f}")
        console.print(table)
    else:
        print(f"   Stocks:       {len(stocks)} ({total_inv:,.0f} invested)")
        print(f"   Mutual Funds: {len(mfs)}")
        print(f"   US Holdings:  {len(us)}")

    # Save
    save_path = save_portfolio(result, config)
    _print(f"\n✅ Portfolio saved: {save_path}", style="bold green")

    errors = result.get("errors", [])
    if errors:
        _print(f"\n⚠️  {len(errors)} warning(s):", style="yellow")
        for e in errors:
            _print(f"   • {e}", style="dim")


# ── DASHBOARD ────────────────────────────────────────────────

def cmd_dashboard(args):
    """Generate HTML dashboard."""
    _banner()
    _print("🎨 Generating dashboard...\n", style="bold")

    config = Config()
    from wealthpulse.core.dashboard import generate_dashboard

    try:
        output = generate_dashboard(config)
        _print(f"✅ Dashboard saved: {output}", style="bold green")

        # Open in browser
        open_browser = input("\nOpen in browser? (Y/n): ").strip().lower()
        if open_browser != "n":
            webbrowser.open(f"file:///{output}")
    except FileNotFoundError as e:
        _print(f"❌ {e}", style="red")
        _print("   Run 'wealthpulse parse' first.", style="dim")
    except Exception as e:
        _print(f"❌ Error: {e}", style="red")


# ── EMAIL ────────────────────────────────────────────────────

def cmd_email(args):
    """Send daily brief email."""
    _banner()
    _print("📧 Sending daily brief...\n", style="bold")

    config = Config()
    from wealthpulse.core.email_sender import send_daily_brief

    success = send_daily_brief(config)
    if not success:
        _print("\n💡 Tip: Run 'wealthpulse setup' to configure email.", style="dim")


# ── DEMO ─────────────────────────────────────────────────────

def cmd_demo(args):
    """Run with sample data to see WealthPulse in action."""
    _banner()
    _print("🎬 Running demo with sample data...\n", style="bold")

    # Load sample portfolio
    sample_dir = Path(__file__).resolve().parent / "samples"
    sample_portfolio = sample_dir / "sample_portfolio.json"

    if not sample_portfolio.exists():
        _print("❌ Sample data not found. Package may be incomplete.", style="red")
        return

    # Create temp config for demo
    demo_config = Config.__new__(Config)
    demo_config._data = {
        "profile": {"name": "Demo Portfolio"},
        "fire": {"target_corpus": 50000000, "target_age": 45, "current_age": 32},
        "dashboard": {"theme": "dark"},
        "non_equity": {"EPF": 800000, "PPF": 500000, "FD": 300000},
        "brokers": {},
        "verdicts": {},
        "email": {},
        "news_feeds": {
            "Market": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx6TVdZU0FtVnVHZ0pKVGlnQVAB",
        },
    }

    # Determine output path
    output_dir = os.path.join(ROOT, "output")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "WealthPulse_DEMO.html")

    from wealthpulse.core.dashboard import generate_dashboard

    try:
        output = generate_dashboard(
            demo_config,
            portfolio_path=str(sample_portfolio),
            output_path=output_path,
        )
        _print(f"✅ Demo dashboard generated: {output}", style="bold green")
        _print("\n🌐 Opening in your browser...", style="cyan")
        webbrowser.open(f"file:///{output}")
    except Exception as e:
        _print(f"❌ Error: {e}", style="red")
        import traceback
        traceback.print_exc()


# ── SCHEDULER ────────────────────────────────────────────────

def cmd_schedule(args):
    """Set up scheduled daily emails (Windows Task Scheduler / cron)."""
    _banner()
    _print("⏰ Setting up daily email schedule...\n", style="bold")

    if sys.platform == "win32":
        _setup_windows_scheduler()
    else:
        _setup_cron()


def _setup_windows_scheduler():
    """Create a Windows Task Scheduler task."""
    import subprocess

    time_str = input("   Send daily brief at what time? (16:00): ").strip() or "16:00"
    python_path = sys.executable
    script_cmd = f'"{python_path}" -m wealthpulse email'

    task_name = "WealthPulse_DailyBrief"

    cmd = (
        f'schtasks /Create /SC WEEKLY /D MON,TUE,WED,THU,FRI '
        f'/TN "{task_name}" /TR "{script_cmd}" /ST {time_str} /F'
    )

    try:
        subprocess.run(cmd, shell=True, check=True)
        _print(f"\n✅ Scheduled: {task_name} at {time_str} (Mon-Fri)", style="bold green")
        _print("   The task will run even if you're logged off.", style="dim")
    except subprocess.CalledProcessError as e:
        _print(f"❌ Failed to create task: {e}", style="red")
        _print("   Try running as Administrator.", style="dim")


def _setup_cron():
    """Show cron setup instructions."""
    python_path = sys.executable
    _print("   Add this line to your crontab (crontab -e):\n", style="")
    _print(f'   0 16 * * 1-5 {python_path} -m wealthpulse email', style="cyan")
    _print("\n   This runs Mon-Fri at 4:00 PM.", style="dim")


# ── MAIN ─────────────────────────────────────────────────────

def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="wealthpulse",
        description="💰 WealthPulse — Your Open-Source Portfolio Dashboard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  setup       Interactive setup wizard
  parse       Parse broker statements → portfolio JSON
  dashboard   Generate HTML portfolio dashboard
  email       Send daily portfolio brief email
  demo        Run with sample data
  schedule    Set up daily email scheduling

Examples:
  wealthpulse setup                  # First-time setup
  wealthpulse demo                   # Try with sample data
  wealthpulse parse && wealthpulse dashboard
        """,
    )

    parser.add_argument("--version", action="version", version=f"WealthPulse {__version__}")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    subparsers.add_parser("setup", help="Interactive setup wizard")
    subparsers.add_parser("parse", help="Parse broker statements")
    subparsers.add_parser("dashboard", help="Generate HTML dashboard")
    subparsers.add_parser("email", help="Send daily brief email")
    subparsers.add_parser("demo", help="Run demo with sample data")
    subparsers.add_parser("schedule", help="Set up daily email scheduling")

    args = parser.parse_args()

    commands = {
        "setup": cmd_setup,
        "parse": cmd_parse,
        "dashboard": cmd_dashboard,
        "email": cmd_email,
        "demo": cmd_demo,
        "schedule": cmd_schedule,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        _banner()
        parser.print_help()
        _print("\n💡 Try: wealthpulse demo\n", style="cyan")
