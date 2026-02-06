"""
Morgan Stanley StockPlan Connect PDF parser.

Parses Morgan Stanley ESPP/RSU account statement PDF.
Extracts shares, share price, and value from the closing value section.
"""

import re
from .base import BaseParser, ParseResult, USHolding


class MorganStanleyParser(BaseParser):
    """Parser for Morgan Stanley StockPlan Connect PDF statements."""

    broker_name = "MorganStanley"
    file_patterns = ["MorganStanley_*.pdf", "morgan_stanley_*.pdf", "MS_*.pdf"]

    def parse(self, filepath: str) -> ParseResult:
        from PyPDF2 import PdfReader
        result = ParseResult(broker_name=self.broker_name)

        try:
            reader = PdfReader(filepath)
        except Exception as e:
            result.errors.append(f"Cannot open PDF {filepath}: {e}")
            return result

        full_text = ""
        for page in reader.pages:
            text = page.extract_text() or ""
            full_text += text + "\n"

        # Extract holdings from Morgan Stanley format
        holding = self._extract_holding(full_text)
        if holding:
            result.us_holdings.append(holding)

        return result

    def _extract_holding(self, text: str) -> USHolding | None:
        """Extract stock holding from Morgan Stanley PDF text."""

        # Detect stock symbol
        common_symbols = ['MSFT', 'AAPL', 'GOOGL', 'AMZN', 'META', 'TSLA', 'NVDA']
        detected_symbol = None
        for sym in common_symbols:
            if sym in text:
                detected_symbol = sym
                break

        if not detected_symbol:
            return None

        # Morgan Stanley patterns:
        # "Number of Shares  XX.XXX"
        # "Share Price  $XXX.XX"
        # "Share Value  $XX,XXX.XX"
        shares_match = re.search(
            r'Number of Shares\s+([\d,]+\.?\d*)', text, re.IGNORECASE
        )
        price_match = re.search(
            r'Share Price\s+\$?([\d,]+\.?\d*)', text, re.IGNORECASE
        )
        value_match = re.search(
            r'Share Value\s+\$?([\d,]+\.?\d*)', text, re.IGNORECASE
        )

        if not shares_match:
            return None

        qty = float(shares_match.group(1).replace(',', ''))
        price = float(price_match.group(1).replace(',', '')) if price_match else 0
        value = float(value_match.group(1).replace(',', '')) if value_match else qty * price

        return USHolding(
            symbol=detected_symbol,
            name=detected_symbol,
            quantity=qty,
            current_price_usd=price,
            value_usd=value,
            source=self.broker_name,
        )
