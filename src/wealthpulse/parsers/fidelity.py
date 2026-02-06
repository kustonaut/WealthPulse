"""
Fidelity NetBenefits PDF parser.

Parses Fidelity NetBenefits account statement PDF for ESPP/RSU holdings.
Extracts stock symbol, number of shares, share price, and total value
using regex patterns.
"""

import re
from .base import BaseParser, ParseResult, USHolding


class FidelityParser(BaseParser):
    """Parser for Fidelity NetBenefits PDF statements."""

    broker_name = "Fidelity"
    file_patterns = ["Fidelity_*.pdf", "fidelity_*.pdf"]

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

        # Look for stock holdings patterns
        # Common patterns in Fidelity statements:
        # "MSFT" or "Microsoft" followed by shares and values
        # "Number of Shares: 123.456"
        # "Share Price: $123.45"
        # "Total Value: $12,345.67"

        holdings = self._extract_holdings(full_text)

        for h in holdings:
            result.us_holdings.append(USHolding(
                symbol=h['symbol'],
                name=h.get('name', h['symbol']),
                quantity=h['quantity'],
                current_price_usd=h.get('price', 0),
                value_usd=h.get('value', 0),
                source=self.broker_name,
            ))

        return result

    def _extract_holdings(self, text: str) -> list[dict]:
        """Extract stock holdings from PDF text."""
        holdings = []

        # Pattern 1: Look for "Your ESPP Account" or similar section
        # then find shares/price/value
        shares_pattern = r'(?:Number of )?Shares[:\s]*([\d,]+\.?\d*)'
        price_pattern = r'(?:Share |Stock )?Price[:\s]*\$?([\d,]+\.?\d*)'
        value_pattern = r'(?:Total |Market )?Value[:\s]*\$?([\d,]+\.?\d*)'

        shares_matches = re.findall(shares_pattern, text, re.IGNORECASE)
        price_matches = re.findall(price_pattern, text, re.IGNORECASE)
        value_matches = re.findall(value_pattern, text, re.IGNORECASE)

        # Try to find stock symbol
        symbol_pattern = r'\b([A-Z]{2,5})\b.*?(?:stock|share|equity)'
        symbol_matches = re.findall(symbol_pattern, text, re.IGNORECASE)

        # Detect common stock symbols in text
        common_symbols = ['MSFT', 'AAPL', 'GOOGL', 'AMZN', 'META', 'TSLA', 'NVDA']
        detected_symbol = None
        for sym in common_symbols:
            if sym in text:
                detected_symbol = sym
                break

        if not detected_symbol and symbol_matches:
            detected_symbol = symbol_matches[0].upper()

        if detected_symbol and shares_matches:
            qty = float(shares_matches[0].replace(',', ''))
            price = float(price_matches[0].replace(',', '')) if price_matches else 0
            value = float(value_matches[0].replace(',', '')) if value_matches else qty * price

            holdings.append({
                'symbol': detected_symbol,
                'name': detected_symbol,
                'quantity': qty,
                'price': price,
                'value': value,
            })

        return holdings
