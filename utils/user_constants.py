#!/usr/bin/env python3
"""
User Constants
This module provides centralized access to environment variables for the trading system.
"""

import os

# API Credentials
API_KEY = os.environ.get("STRATEGY_API_KEY", "")
SECRET_KEY = os.environ.get("STRATEGY_API_SECRET", "")
PASSPHRASE = os.environ.get("STRATEGY_PASSPHRASE", "")

# Exchange Configuration
EXCHANGE = os.environ.get("EXCHANGE", "")
PAPER_MODE = os.environ.get("PAPER_TRADING", False)
