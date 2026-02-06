"""
National Pension System (NPS) statement parser.

Parses NPS Transaction Statement PDF from CRA (NSDL / KFintech).
Download: npscra.nsdl.co.in → Transaction Statement → Download PDF
  OR: cra-nsdl.com → Login → Statement → Transaction Statement

The NPS statement PDF typically contains:
  - PRAN number
  - Subscriber name
  - Scheme details (Tier I / Tier II)
  - Pension Fund Manager (PFM)
  - Asset class allocation (E/C/G/A)
  - Contribution summary (Employee, Employer, Voluntary)
  - NAV, units, total value

This parser uses regex to extract key data from PDF text.
"""

import re
from .base import BaseParser, ParseResult, NPSHolding


class NPSParser(BaseParser):
    """Parser for NPS Transaction Statement PDF."""

    broker_name = "NPS"
    file_patterns = [
        "NPS_*.pdf", "nps_*.pdf", "NPS_*.PDF",
        "NSDL_NPS_*.pdf", "nps_statement_*.pdf",
        "TransactionStatement_*.pdf",
        "NPS-SOT*.pdf",  # NPS Statement of Transaction
    ]

    def parse(self, filepath: str) -> ParseResult:
        result = ParseResult(broker_name=self.broker_name)

        try:
            text = self._extract_text(filepath)
        except Exception as e:
            result.errors.append(f"Cannot read NPS PDF {filepath}: {e}")
            return result

        if not text or len(text) < 100:
            result.errors.append("NPS PDF appears empty or unreadable")
            return result

        # Extract PRAN
        pran = ""
        pran_match = re.search(r'PRAN\s*[:\-]?\s*(\d{12})', text, re.IGNORECASE)
        if pran_match:
            pran = pran_match.group(1)

        # Extract statement date
        date_match = re.search(
            r'(?:as\s+on|statement\s+date|date\s*:)\s*[:\-]?\s*(\d{1,2}[\-/]\w{3}[\-/]\d{4}|\d{1,2}[\-/]\d{1,2}[\-/]\d{4})',
            text, re.IGNORECASE
        )
        if date_match:
            result.statement_date = date_match.group(1)

        # --- Strategy 1: Find Tier-level summary with total corpus ---
        # Look for patterns like:
        #   "Tier I" ... "Total Value" ... "₹1,23,456.78"
        #   "Closing Balance" ... "1,23,456.78"
        tier_data = {}
        for tier in ['I', 'II']:
            tier_pattern = rf'Tier\s*{tier}\b'
            tier_match = re.search(tier_pattern, text, re.IGNORECASE)
            if not tier_match:
                continue

            # Extract text block after this tier heading
            block_start = tier_match.end()
            # Find next "Tier" heading or end of text
            next_tier = re.search(r'Tier\s*(I{1,2})\b', text[block_start:], re.IGNORECASE)
            block_end = block_start + next_tier.start() if next_tier else len(text)
            block = text[block_start:block_end]

            tier_data[f"Tier {tier}"] = block

        # --- Strategy 2: Find contribution and corpus amounts ---
        # Common patterns in NPS statements
        holdings_found = []

        # Try to extract scheme-wise breakdown
        # Pattern: "Scheme E" or "Asset Class E" or "Equity (E)" with value
        for asset_class, desc in [('E', 'Equity'), ('C', 'Corporate Bonds'),
                                   ('G', 'Government Securities'), ('A', 'Alternative')]:
            for tier_name, block in tier_data.items():
                # Look for amount near asset class mention
                class_patterns = [
                    rf'{desc}\s*\({asset_class}\).*?(\d[\d,]*\.?\d*)',
                    rf'(?:Scheme|Class)\s*{asset_class}\b.*?(\d[\d,]*\.?\d*)',
                    rf'{asset_class}\s*[-–]\s*{desc}.*?(\d[\d,]*\.?\d*)',
                ]
                for pat in class_patterns:
                    m = re.search(pat, block, re.IGNORECASE)
                    if m:
                        value = _parse_amount(m.group(1))
                        if value > 100:  # Sanity check
                            holdings_found.append(NPSHolding(
                                pran=pran,
                                scheme_name=tier_name,
                                asset_class=asset_class,
                                current_value=value,
                                statement_date=result.statement_date or '',
                            ))
                        break

        # --- Strategy 3: Look for total corpus value ---
        # If scheme-wise extraction failed, try to get total
        if not holdings_found:
            total_patterns = [
                r'(?:total|closing)\s*(?:balance|value|corpus|amount)\s*[:\-]?\s*₹?\s*([\d,]+\.?\d*)',
                r'(?:net\s+asset\s+value|nav)\s*[:\-]?\s*₹?\s*([\d,]+\.?\d*)',
                r'total\s+(?:tier\s+[iI1])\s*[:\-]?\s*₹?\s*([\d,]+\.?\d*)',
            ]
            for pat in total_patterns:
                matches = re.findall(pat, text, re.IGNORECASE)
                for m in matches:
                    value = _parse_amount(m)
                    if value > 1000:  # Reasonable NPS balance
                        holdings_found.append(NPSHolding(
                            pran=pran,
                            scheme_name="Tier I",
                            current_value=value,
                            statement_date=result.statement_date or '',
                        ))
                        break
                if holdings_found:
                    break

        # --- Extract contribution totals ---
        contrib_patterns = [
            r'(?:total\s+)?(?:employee|subscriber)\s*contribution\s*[:\-]?\s*₹?\s*([\d,]+\.?\d*)',
            r'(?:total\s+)?employer\s*contribution\s*[:\-]?\s*₹?\s*([\d,]+\.?\d*)',
        ]
        total_contribution = 0
        for pat in contrib_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                total_contribution += _parse_amount(m.group(1))

        # Set contribution on holdings
        for h in holdings_found:
            if total_contribution > 0 and h.contribution_total == 0:
                h.contribution_total = total_contribution

        # --- Extract Fund Manager name ---
        pfm_patterns = [
            r'(?:pension\s+fund\s*(?:manager)?|pfm|fund\s+manager)\s*[:\-]?\s*([A-Z][A-Za-z\s&]+?)(?:\n|,|\d)',
            r'(SBI|HDFC|ICICI|UTI|Kotak|LIC|Aditya Birla|Tata)\s*(?:Pension|PFM)',
        ]
        fund_manager = ""
        for pat in pfm_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                fund_manager = m.group(1).strip()
                break

        for h in holdings_found:
            h.fund_manager = fund_manager

        # --- Extract NAV and Units ---
        nav_match = re.search(r'NAV\s*[:\-]?\s*₹?\s*([\d,]+\.?\d+)', text, re.IGNORECASE)
        units_match = re.search(r'(?:total\s+)?units?\s*[:\-]?\s*([\d,]+\.?\d+)', text, re.IGNORECASE)
        if nav_match:
            for h in holdings_found:
                if h.nav == 0:
                    h.nav = _parse_amount(nav_match.group(1))
        if units_match:
            for h in holdings_found:
                if h.units == 0:
                    h.units = _parse_amount(units_match.group(1))

        result.nps_holdings = holdings_found

        if not holdings_found:
            result.errors.append(
                "Could not extract NPS data from PDF. "
                "The PDF format may differ — try downloading a fresh statement from npscra.nsdl.co.in"
            )

        return result

    def _extract_text(self, filepath: str) -> str:
        """Extract text from PDF using PyPDF2."""
        from PyPDF2 import PdfReader
        reader = PdfReader(filepath)
        text_parts = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
        return '\n'.join(text_parts)


def _parse_amount(s: str) -> float:
    """Parse an Indian-format amount string to float."""
    try:
        return float(s.replace(',', '').strip())
    except (ValueError, TypeError):
        return 0.0
