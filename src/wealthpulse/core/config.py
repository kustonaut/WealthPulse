"""
Configuration loader for WealthPulse.

Handles loading config.yaml, validating settings, and providing defaults.
"""

import os
import yaml
from pathlib import Path
from typing import Any, Optional


# Project directories
def get_project_root() -> Path:
    """Get the project root directory (where config/ and data/ live)."""
    # Walk up from this file to find pyproject.toml or config/
    current = Path(__file__).resolve().parent
    for _ in range(5):
        if (current / 'config').exists() or (current / 'pyproject.toml').exists():
            return current
        current = current.parent
    # Fallback: current working directory
    return Path.cwd()


ROOT = get_project_root()
CONFIG_DIR = ROOT / 'config'
DATA_DIR = ROOT / 'data'
STATEMENTS_DIR = DATA_DIR / 'statements'
OUTPUT_DIR = DATA_DIR / 'output'

# Default configuration
DEFAULTS = {
    'profile': {
        'name': 'Investor',
        'age': 30,
        'currency': 'INR',
        'usd_to_inr': 87.50,
    },
    'fire': {
        'target_amount': 100000000,
        'target_age': 45,
        'monthly_expenses': 100000,
        'expected_return_pct': 12,
        'inflation_pct': 6,
    },
    'brokers': {
        'groww': {'enabled': True},
        'zerodha': {'enabled': True},
        'mutual_funds': {'enabled': True},
        'fidelity': {'enabled': False},
        'morgan_stanley': {'enabled': False},
    },
    'non_equity': {
        'nps': 0, 'epf': 0, 'ppf': 0, 'fd': 0,
        'bonds': 0, 'gold': 0, 'real_estate': 0, 'cash': 0, 'crypto': 0,
    },
    'email': {
        'enabled': False,
        'smtp_server': 'smtp.gmail.com',
        'smtp_port': 465,
        'sender_email': '',
        'app_password': '',
        'recipient_email': '',
    },
    'dashboard': {
        'theme': 'dark',
        'show_fire_progress': True,
        'show_sector_chart': True,
        'show_market_movers': True,
        'show_news': True,
        'top_n_movers': 5,
    },
    'news_feeds': {
        'NIFTY 50': 'https://news.google.com/rss/search?q=nifty+50+stock+market&hl=en-IN',
        'Market': 'https://news.google.com/rss/search?q=indian+stock+market+today&hl=en-IN',
    },
}


class Config:
    """Configuration manager for WealthPulse."""

    def __init__(self, config_path: Optional[str] = None):
        self._data = dict(DEFAULTS)
        self._config_path = config_path or str(CONFIG_DIR / 'config.yaml')
        self._load()

    def _load(self):
        """Load config from YAML file, falling back to defaults."""
        if os.path.exists(self._config_path):
            with open(self._config_path, 'r', encoding='utf-8') as f:
                user_config = yaml.safe_load(f) or {}
            self._deep_merge(self._data, user_config)

    def _deep_merge(self, base: dict, override: dict):
        """Deep merge override into base dict."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Get a config value by dot-separated key. E.g., 'profile.name'."""
        keys = key.split('.')
        val = self._data
        for k in keys:
            if isinstance(val, dict) and k in val:
                val = val[k]
            else:
                return default
        return val

    @property
    def profile(self) -> dict:
        return self._data.get('profile', {})

    @property
    def fire(self) -> dict:
        return self._data.get('fire', {})

    @property
    def brokers(self) -> dict:
        return self._data.get('brokers', {})

    @property
    def non_equity(self) -> dict:
        return self._data.get('non_equity', {})

    @property
    def email(self) -> dict:
        return self._data.get('email', {})

    @property
    def dashboard(self) -> dict:
        return self._data.get('dashboard', {})

    @property
    def news_feeds(self) -> dict:
        return self._data.get('news_feeds', {})

    @property
    def verdicts(self) -> dict:
        return self._data.get('verdicts', {})

    def is_broker_enabled(self, broker: str) -> bool:
        return self.brokers.get(broker, {}).get('enabled', False)

    def save(self):
        """Save current config to YAML."""
        os.makedirs(os.path.dirname(self._config_path), exist_ok=True)
        with open(self._config_path, 'w', encoding='utf-8') as f:
            yaml.dump(self._data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    def ensure_dirs(self):
        """Create required data directories."""
        for d in [CONFIG_DIR, DATA_DIR, STATEMENTS_DIR, OUTPUT_DIR]:
            d.mkdir(parents=True, exist_ok=True)
