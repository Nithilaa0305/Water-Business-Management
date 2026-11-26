"""Application logging configuration."""

import logging
import sys
from app.config.settings import LOG_DIR


def setup_logger(name: str = "water_app") -> logging.Logger:
    """Setup and return application logger writing to console and local file."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)
    
    # File handler
    log_file = LOG_DIR / "app.log"
    try:
        file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.DEBUG)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"Warning: Could not initialize log file: {e}")
        
    return logger


logger = setup_logger()
