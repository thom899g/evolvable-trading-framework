"""
Real-time market data fetcher with caching and error resilience.
Handles multiple exchanges and provides clean, normalized data.
"""
import asyncio
import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass
from enum import Enum

import ccxt
import pandas as pd
import numpy as np
from ccxt import NetworkError, ExchangeError

from config import ExchangeType, config_manager