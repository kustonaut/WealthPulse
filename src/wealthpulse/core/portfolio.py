"""
Portfolio consolidation engine.

Parses all enabled broker statements, consolidates holdings,
and generates the unified portfolio_data.json.
"""

import json
import os
from datetime import datetime
from dataclasses import asdict

from .config import Config, STATEMENTS_DIR, DATA_DIR
from ..parsers.base import ParseResult, StockHolding

# Indian brokers
from ..parsers.groww import GrowwParser
from ..parsers.zerodha import ZerodhaParser
from ..parsers.mutual_funds import MutualFundParser
from ..parsers.angel_one import AngelOneParser
from ..parsers.upstox import UpstoxParser
from ..parsers.icici_direct import ICICIDirectParser
from ..parsers.hdfc_securities import HDFCSecuritiesParser
from ..parsers.kotak import KotakSecuritiesParser
from ..parsers.dhan import DhanParser
from ..parsers.five_paisa import FivePaisaParser

# US brokers
from ..parsers.fidelity import FidelityParser
from ..parsers.morgan_stanley import MorganStanleyParser

# Retirement / Government
from ..parsers.nps import NPSParser
from ..parsers.epfo import EPFOParser


# Parser registry — add new parsers here
PARSER_REGISTRY = {
    # Indian brokers
    'groww': GrowwParser,
    'zerodha': ZerodhaParser,
    'mutual_funds': MutualFundParser,
    'angel_one': AngelOneParser,
    'upstox': UpstoxParser,
    'icici_direct': ICICIDirectParser,
    'hdfc_securities': HDFCSecuritiesParser,
    'kotak_securities': KotakSecuritiesParser,
    'dhan': DhanParser,
    'five_paisa': FivePaisaParser,
    # US brokers
    'fidelity': FidelityParser,
    'morgan_stanley': MorganStanleyParser,
    # Retirement / Government
    'nps': NPSParser,
    'epfo': EPFOParser,
}


def parse_all_statements(config: Config, statements_dir: str = None) -> dict:
    """
    Parse all enabled broker statements and return consolidated portfolio data.

    Args:
        config: WealthPulse configuration
        statements_dir: Directory containing statement files (default: data/statements/)

    Returns:
        Consolidated portfolio dict ready to save as JSON
    """
    src_dir = statements_dir or str(STATEMENTS_DIR)
    results: list[ParseResult] = []
    parsed_files = []

    print(f"\n{'='*60}")
    print(f"  📁 Parsing statements from: {src_dir}")
    print(f"{'='*60}\n")

    for broker_key, parser_class in PARSER_REGISTRY.items():
        if not config.is_broker_enabled(broker_key):
            continue

        parser = parser_class()
        filepath = parser.find_latest_file(src_dir)

        if not filepath:
            print(f"  ⚠️  No {parser.broker_name} file found (patterns: {parser.file_patterns})")
            continue

        print(f"  📄 Parsing {parser.broker_name}: {os.path.basename(filepath)}")
        result = parser.parse(filepath)

        if result.errors:
            for err in result.errors:
                print(f"    ❌ {err}")
        else:
            stock_count = len(result.stocks)
            mf_count = len(result.mutual_funds)
            us_count = len(result.us_holdings)
            nps_count = len(result.nps_holdings)
            epfo_count = len(result.epfo_holdings)
            parts = []
            if stock_count: parts.append(f"{stock_count} stocks")
            if mf_count: parts.append(f"{mf_count} MFs")
            if us_count: parts.append(f"{us_count} US holdings")
            if nps_count: parts.append(f"{nps_count} NPS schemes")
            if epfo_count: parts.append(f"{epfo_count} EPFO accounts")
            print(f"    ✅ {', '.join(parts) if parts else 'No holdings found'}")
            results.append(result)
            parsed_files.append(os.path.basename(filepath))

    # Consolidate
    return _consolidate(config, results, parsed_files)


def _consolidate(config: Config, results: list[ParseResult], parsed_files: list[str]) -> dict:
    """Consolidate all parse results into a unified portfolio dict."""
    print(f"\n🔗 Consolidating holdings...")

    # Load existing data to preserve verdicts
    existing = _load_existing()
    existing_verdicts = existing.get('stock_verdicts', {})

    # ---- Indian Stocks ----
    all_stocks: list[StockHolding] = []
    for r in results:
        all_stocks.extend(r.stocks)

    consolidated_stocks = {}
    for stock in all_stocks:
        sym = stock.symbol
        if sym not in consolidated_stocks:
            consolidated_stocks[sym] = {
                'symbol': sym,
                'total_qty': 0,
                'total_invested': 0,
                'total_closing_value': 0,
                'brokers': [],
            }
        consolidated_stocks[sym]['total_qty'] += stock.quantity
        consolidated_stocks[sym]['total_invested'] += stock.invested
        consolidated_stocks[sym]['total_closing_value'] += stock.closing_value
        consolidated_stocks[sym]['brokers'].append({
            'broker': stock.broker,
            'qty': stock.quantity,
            'avg_price': stock.avg_price,
            'invested': stock.invested,
            'closing_price': stock.closing_price,
            'closing_value': stock.closing_value,
        })

    # Calculate blended avg price
    for sym, data in consolidated_stocks.items():
        if data['total_qty'] > 0:
            data['blended_avg_price'] = round(data['total_invested'] / data['total_qty'], 2)
        else:
            data['blended_avg_price'] = 0

    # ---- Mutual Funds ----
    all_mfs = []
    for r in results:
        for mf in r.mutual_funds:
            all_mfs.append({
                'name': mf.name,
                'amc': mf.amc,
                'category': mf.sub_category or mf.category,
                'type': mf.category,
                'invested': mf.invested,
                'current': mf.current,
                'xirr': mf.xirr,
                'num_folios': 1,
            })

    # ---- US Holdings ----
    us_holdings = {}
    for r in results:
        for h in r.us_holdings:
            sym = h.symbol
            if sym not in us_holdings:
                us_holdings[sym] = {
                    'symbol': sym,
                    'name': h.name,
                    'total_qty': 0,
                    'total_invested_usd': 0,
                    'total_value_usd': 0,
                    'sources': [],
                }
            us_holdings[sym]['total_qty'] += h.quantity
            us_holdings[sym]['total_value_usd'] += h.value_usd
            us_holdings[sym]['sources'].append({
                'source': h.source,
                'qty': h.quantity,
                'value_usd': h.value_usd,
            })

    # ---- NPS Holdings ----
    nps_holdings = []
    for r in results:
        for h in r.nps_holdings:
            nps_holdings.append({
                'pran': h.pran,
                'scheme_name': h.scheme_name,
                'fund_manager': h.fund_manager,
                'asset_class': h.asset_class,
                'nav': h.nav,
                'units': h.units,
                'contribution_total': h.contribution_total,
                'current_value': h.current_value,
                'statement_date': h.statement_date,
            })

    # ---- EPFO Holdings ----
    epfo_holdings = []
    for r in results:
        for h in r.epfo_holdings:
            epfo_holdings.append({
                'uan': h.uan,
                'member_id': h.member_id,
                'establishment': h.establishment,
                'employee_share': h.employee_share,
                'employer_share': h.employer_share,
                'pension_share': h.pension_share,
                'total_balance': h.total_balance,
                'interest_earned': h.interest_earned,
                'statement_date': h.statement_date,
            })

    # ---- Verdicts ----
    verdicts = dict(existing_verdicts)
    # Add config-based verdicts
    for sym, v in config.verdicts.items():
        verdicts[sym] = v
    # Add default verdicts for new stocks
    new_stocks = []
    for sym in consolidated_stocks:
        if sym not in verdicts:
            verdicts[sym] = {
                'verdict': 'HOLD', 'risk': 'Medium', 'sector': 'Other',
                'pe': 0, 'roe': 0, 'roce': 0,
                'target_1m': 0, 'target_1y': 0, 'target_5y': 0,
            }
            new_stocks.append(sym)

    if new_stocks:
        print(f"  🆕 New stocks (need verdict review): {', '.join(new_stocks)}")

    # ---- Yahoo Finance ticker map ----
    yahoo_map = {}
    for sym in consolidated_stocks:
        if not sym.startswith('INE') and not sym.endswith('-RR'):
            yahoo_map[sym] = f"{sym}.NS"

    # ---- Build final portfolio dict ----
    total_eq_inv = sum(s['total_invested'] for s in consolidated_stocks.values())
    total_eq_close = sum(s['total_closing_value'] for s in consolidated_stocks.values())
    total_mf_inv = sum(m['invested'] for m in all_mfs)
    total_mf_cur = sum(m['current'] for m in all_mfs)
    total_us_usd = sum(h['total_value_usd'] for h in us_holdings.values())
    total_nps = sum(h['current_value'] for h in nps_holdings)
    total_epfo = sum(h['total_balance'] for h in epfo_holdings)

    portfolio = {
        '_metadata': {
            'generated_at': datetime.now().isoformat(),
            'source_files': parsed_files,
            'stock_count': len(consolidated_stocks),
            'mf_count': len(all_mfs),
            'us_count': len(us_holdings),
            'nps_count': len(nps_holdings),
            'epfo_count': len(epfo_holdings),
        },
        'stocks': consolidated_stocks,
        'stock_verdicts': verdicts,
        'yahoo_map': yahoo_map,
        'mutual_funds': all_mfs,
        'us_holdings': us_holdings,
        'nps_holdings': nps_holdings,
        'epfo_holdings': epfo_holdings,
        'non_equity': dict(config.non_equity),
    }

    # Print summary
    ne = config.non_equity
    ne_total = sum(ne.values())
    print(f"\n{'='*60}")
    print(f"  📊 SUMMARY")
    print(f"{'='*60}")
    print(f"  🇮🇳 Stocks:      {len(consolidated_stocks)} stocks, invested ₹{total_eq_inv:,.0f}")
    if total_eq_close > 0:
        print(f"                   closing value ₹{total_eq_close:,.0f}")
    print(f"  📊 Mutual Funds: {len(all_mfs)} funds, invested ₹{total_mf_inv:,.0f}, current ₹{total_mf_cur:,.0f}")
    if us_holdings:
        print(f"  🇺🇸 US Holdings: {len(us_holdings)} stocks, ${total_us_usd:,.2f}")
    if nps_holdings:
        print(f"  🏛️  NPS:         {len(nps_holdings)} schemes, corpus ₹{total_nps:,.0f}")
    if epfo_holdings:
        print(f"  🏦 EPFO:        {len(epfo_holdings)} accounts, balance ₹{total_epfo:,.0f}")
    if ne_total > 0:
        parts = [f"{k.upper()} ₹{v:,}" for k, v in ne.items() if v > 0]
        print(f"  🏦 Non-Equity:   {' | '.join(parts)}")

    return portfolio


def _load_existing() -> dict:
    """Load existing portfolio_data.json to preserve verdicts."""
    json_path = DATA_DIR / 'portfolio_data.json'
    if json_path.exists():
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_portfolio(portfolio: dict, output_path: str = None):
    """Save consolidated portfolio data to JSON."""
    if output_path is None:
        output_path = str(DATA_DIR / 'portfolio_data.json')

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(portfolio, f, indent=2, ensure_ascii=False)

    size = os.path.getsize(output_path)
    print(f"\n  ✅ Saved: {output_path}")
    print(f"     File size: {size:,} bytes")
    print(f"{'='*60}")
    return output_path


def load_portfolio(json_path: str = None) -> dict:
    """Load portfolio data from JSON file."""
    if json_path is None:
        json_path = str(DATA_DIR / 'portfolio_data.json')

    if not os.path.exists(json_path):
        raise FileNotFoundError(
            f"Portfolio data not found at {json_path}.\n"
            "Run 'wealthpulse parse' first to generate it from your statements."
        )

    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)
