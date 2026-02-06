"""
Base parser interface for WealthPulse broker statement parsers.

To add a new broker, create a class that inherits from BaseParser
and implement the `parse()` method.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
import os
import glob


@dataclass
class StockHolding:
    """A single stock holding from a broker statement."""
    symbol: str
    isin: str = ""
    quantity: float = 0
    avg_price: float = 0
    invested: float = 0
    closing_price: float = 0
    closing_value: float = 0
    broker: str = ""
    sector: str = ""


@dataclass
class MutualFundHolding:
    """A single mutual fund holding."""
    name: str
    amc: str = ""
    category: str = ""          # Equity, Hybrid, Debt
    sub_category: str = ""      # Flexi Cap, Small Cap, ELSS, Arbitrage, etc.
    folio: str = ""
    invested: float = 0
    current: float = 0
    xirr: float = 0
    units: float = 0
    source: str = ""


@dataclass
class USHolding:
    """A US equity holding (ESPP, RSU, etc.)."""
    symbol: str
    name: str = ""
    quantity: float = 0
    avg_price_usd: float = 0
    current_price_usd: float = 0
    invested_usd: float = 0
    value_usd: float = 0
    source: str = ""


@dataclass
class NPSHolding:
    """National Pension System holding."""
    pran: str = ""                    # PRAN number
    scheme_name: str = ""             # Scheme name (Tier I / Tier II)
    fund_manager: str = ""            # PFM name (SBI, HDFC, etc.)
    asset_class: str = ""             # E (Equity), C (Corporate Bonds), G (Govt), A (Alternate)
    nav: float = 0
    units: float = 0
    contribution_total: float = 0     # Total contributions
    current_value: float = 0          # Current corpus value
    statement_date: str = ""


@dataclass
class EPFOHolding:
    """Employee Provident Fund holding."""
    uan: str = ""                     # Universal Account Number
    member_id: str = ""
    establishment: str = ""           # Employer name
    employee_share: float = 0         # Employee contribution
    employer_share: float = 0         # Employer contribution
    pension_share: float = 0          # EPS contribution
    total_balance: float = 0          # Total EPF balance
    interest_earned: float = 0
    statement_date: str = ""


@dataclass
class ParseResult:
    """Result from parsing a broker statement."""
    stocks: list[StockHolding] = field(default_factory=list)
    mutual_funds: list[MutualFundHolding] = field(default_factory=list)
    us_holdings: list[USHolding] = field(default_factory=list)
    nps_holdings: list[NPSHolding] = field(default_factory=list)
    epfo_holdings: list[EPFOHolding] = field(default_factory=list)
    statement_date: Optional[str] = None
    broker_name: str = ""
    errors: list[str] = field(default_factory=list)


class BaseParser(ABC):
    """
    Base class for all broker statement parsers.

    To add a new broker:
    1. Create a new file in wealthpulse/parsers/ (e.g., my_broker.py)
    2. Inherit from BaseParser
    3. Implement parse(filepath) -> ParseResult
    4. Add your broker to config.example.yaml

    Example:
        class MyBrokerParser(BaseParser):
            broker_name = "MyBroker"
            file_patterns = ["MyBroker_*.xlsx"]

            def parse(self, filepath: str) -> ParseResult:
                # Your parsing logic here
                return ParseResult(stocks=[...], broker_name=self.broker_name)
    """

    broker_name: str = "Unknown"
    file_patterns: list[str] = []

    @abstractmethod
    def parse(self, filepath: str) -> ParseResult:
        """Parse a broker statement file and return holdings."""
        ...

    def find_latest_file(self, directory: str) -> Optional[str]:
        """Find the most recent file matching this parser's patterns."""
        candidates = []
        for pattern in self.file_patterns:
            matches = glob.glob(os.path.join(directory, pattern))
            candidates.extend(matches)

        if not candidates:
            return None

        # Return the most recently modified file
        return max(candidates, key=os.path.getmtime)

    def _normalize_symbol(self, symbol: str) -> str:
        """Normalize stock symbols (strip series suffixes, etc.)."""
        symbol = symbol.strip()
        # Strip exchange series suffixes: RAJESHEXPO-Z → RAJESHEXPO, SILVERBEES-E → SILVERBEES
        if '-' in symbol and len(symbol.split('-')[-1]) <= 2:
            base = symbol.rsplit('-', 1)[0]
            suffix = symbol.rsplit('-', 1)[1]
            # Keep -RR (REIT suffix) and known suffixes, strip exchange series
            if suffix not in ('RR',):
                symbol = base
        return symbol
