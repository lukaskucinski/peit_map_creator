"""
Logging configuration for PEIT Map Creator.

This module provides centralized logging configuration for both console and file output.
Console displays INFO-level messages for user feedback, while file captures DEBUG-level
details for troubleshooting.

Functions:
    setup_logging: Initialize logging handlers and return log file path
    get_logger: Get a logger instance for a specific module

Example:
    >>> from utils.logger import setup_logging, get_logger
    >>> log_file = setup_logging()
    >>> logger = get_logger(__name__)
    >>> logger.info("Processing started")
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional


def setup_logging(log_dir: Optional[Path] = None) -> Path:
    """
    Setup logging to console and file.

    Creates two handlers:
    - Console: INFO level with clean formatting
    - File: DEBUG level with timestamps and module names

    Parameters:
    -----------
    log_dir : Optional[Path]
        Directory for log files. Defaults to PROJECT_ROOT/logs

    Returns:
    --------
    Path
        Path to the created log file
    """
    if log_dir is None:
        log_dir = Path(__file__).parent.parent / 'logs'
    log_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f'peit_{timestamp}.log'

    # Get root logger for peit
    logger = logging.getLogger('peit')
    logger.setLevel(logging.DEBUG)

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Console handler (INFO level) - clean output for users
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console_fmt = logging.Formatter('%(message)s')
    console.setFormatter(console_fmt)

    # File handler (DEBUG level) - detailed output for debugging
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_fmt = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_fmt)

    logger.addHandler(console)
    logger.addHandler(file_handler)

    # Log the setup
    logger.debug(f"Logging initialized: {log_file}")

    return log_file


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.

    Parameters:
    -----------
    name : str
        Module name (typically __name__)

    Returns:
    --------
    logging.Logger
        Configured logger instance

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Module initialized")
    """
    return logging.getLogger(f'peit.{name}')
