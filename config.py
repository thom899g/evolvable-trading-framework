"""
Core configuration management with Firebase integration.
Provides centralized configuration with environment-aware settings.
"""
import os
import json
from typing import Dict, Any, Optional
from enum import Enum
from dataclasses import dataclass
from pathlib import Path
import logging

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from pydantic import BaseModel, ValidationError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize logging
logger = logging.getLogger(__name__)

class TradingMode(str, Enum):
    """Trading execution modes"""
    PAPER = "paper"
    LIVE = "live"
    BACKTEST = "backtest"

class ExchangeType(str, Enum):
    """Supported exchange types"""
    BINANCE = "binance"
    COINBASE = "coinbase"
    KRAKEN = "kraken"
    BYBIT = "bybit"

@dataclass
class StrategyConfig:
    """Strategy configuration container"""
    name: str
    version: str
    parameters: Dict[str, Any]
    risk_per_trade: float = 0.02
    max_open_trades: int = 5
    timeframes: list = None
    
    def __post_init__(self):
        if self.timeframes is None:
            self.timeframes = ["1h", "4h", "1d"]

class FirebaseConfig:
    """Firebase configuration and connection manager"""
    
    _instance = None
    _db = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self.initialize_firebase()
    
    @classmethod
    def initialize_firebase(cls):
        """Initialize Firebase connection with error handling"""
        try:
            # Check for Firebase credentials
            cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
            if not cred_path or not Path(cred_path).exists():
                logger.error("Firebase credentials file not found. Using Firestore emulator if available.")
                # Try to use emulator for development
                os.environ["FIRESTORE_EMULATOR_HOST"] = "localhost:8080"
                cred = credentials.Certificate(None)  # Anonymous credentials
            else:
                cred = credentials.Certificate(cred_path)
            
            # Initialize only if not already initialized
            if not firebase_admin._apps:
                firebase_admin.initialize_app(cred)
            
            cls._db = firestore.client()
            cls._initialized = True
            logger.info("Firebase initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {str(e)}")
            cls._initialized = False
            # Continue without Firebase - system will use fallback storage
    
    @classmethod
    def get_db(cls):
        """Get Firestore database instance with lazy initialization"""
        if not cls._initialized:
            cls.initialize_firebase()
        return cls._db

class TradingConfig(BaseModel):
    """Main trading configuration schema"""
    mode: TradingMode = TradingMode.PAPER
    exchange: ExchangeType = ExchangeType.BINANCE
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    symbols: list = ["BTC/USDT", "ETH/USDT"]
    update_interval: int = 60  # seconds
    
    class Config:
        env_file = ".env"
        use_enum_values = True

class ConfigManager:
    """Centralized configuration manager with Firebase sync"""
    
    def __init__(self):
        self.config = None
        self.firebase_config = FirebaseConfig()
        self.db = self.firebase_config.get_db()
        self._load_config()
    
    def _load_config(self):
        """Load configuration with fallback strategy"""
        try:
            # Try to load from Firebase first
            if self.db:
                doc_ref = self.db.collection("config").document("trading_config")
                doc = doc_ref.get()
                if doc.exists:
                    self.config = TradingConfig(**doc.to_dict())
                    logger.info("Loaded configuration from Firebase")
                    return
        except Exception as e:
            logger.warning(f"Could not load from Firebase: {str(e)}")
        
        # Fallback to environment variables
        try:
            self.config = TradingConfig(
                mode=os.getenv("TRADING_MODE", "paper"),
                exchange=os.getenv("EXCHANGE", "binance"),
                api_key=os.getenv("API_KEY"),
                api_secret=os.getenv("API_SECRET"),
                symbols=json.loads(os.getenv("SYMBOLS", '["BTC/USDT"]')),
                update_interval=int(os.getenv("UPDATE_INTERVAL", "60"))
            )
            logger.info("Loaded configuration from environment")
        except ValidationError as e:
            logger.error(f"Configuration validation failed: {str(e)}")
            raise
    
    def save_config(self, config_data: Dict[str, Any]):
        """Save configuration to Firebase"""
        try:
            if self.db:
                doc_ref = self.db.collection("config").document("trading_config")
                doc_ref.set(config_data)
                logger.info("Configuration saved to Firebase")
        except Exception as e:
            logger.error(f"Failed to save configuration: {str(e)}")

# Global configuration instance
config_manager = ConfigManager()