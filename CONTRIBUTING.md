# Contributing to WealthPulse

Thank you for your interest in contributing! 🎉

## How to Contribute

### 1. Fork & Clone

```bash
git clone https://github.com/your-username/WealthPulse.git
cd WealthPulse
pip install -e ".[dev]"
```

### 2. Run Demo to Verify Setup

```bash
wealthpulse demo
```

### 3. Make Your Changes

- Create a feature branch: `git checkout -b feature/my-feature`
- Write clean, documented code
- Test your changes

### 4. Submit a PR

- Push to your fork
- Open a Pull Request with a clear description

## Ideas for Contributions

### New Broker Parsers
- Angel One / Angel Broking
- Upstox
- Dhan
- 5paisa
- Kotak Securities
- ICICI Direct
- Vanguard (US)
- Charles Schwab (US)

### Feature Ideas
- Historical portfolio tracking (net worth over time)
- Tax harvesting suggestions
- Dividend tracking and yield calculations
- PDF export of dashboard
- Mobile-first responsive design
- SIP calculator integration
- Sector rebalancing suggestions
- Multi-currency support (beyond INR + USD)

### Infrastructure
- Unit tests with pytest
- CI/CD with GitHub Actions
- Docker support
- Web server mode (Flask/FastAPI for live dashboard)

## Code Style

- Python 3.10+ with type hints
- Use `ruff` for linting: `ruff check .`
- Use `black` for formatting: `black .`
- Follow existing patterns in the codebase

## Adding a New Parser

See the [README](README.md#-adding-a-custom-parser) for a step-by-step guide.

## Questions?

Open an issue — we're happy to help!
