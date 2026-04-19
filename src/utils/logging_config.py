"""
Logging Configuration for Mavi Lojistik - PHASE 5

Provides comprehensive logging with:
- Daily log files with date stamps
- File rotation (5MB max, 5 backup files)
- Console output for development
- Structured log format
- UTF-8 encoding for Turkish characters
- Performance monitoring decorator
"""

import logging
import os
import time
from logging.handlers import RotatingFileHandler
from datetime import datetime
from functools import wraps


def setup_logger(name: str, log_dir: str = 'logs') -> logging.Logger:
    """
    Setup unified logger with daily log files and rotation.
    
    Args:
        name: Logger name
        log_dir: Directory for log files
        
    Returns:
        Configured logger instance
    """
    os.makedirs(log_dir, exist_ok=True)
    
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # Console handler (INFO level)
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console_fmt = logging.Formatter('%(levelname)s: %(message)s')
    console.setFormatter(console_fmt)
    
    # File handler (DEBUG level, 5MB rotation, daily files)
    log_file = os.path.join(log_dir, f'{name}_{datetime.now():%Y%m%d}.log')
    file_handler = RotatingFileHandler(
        log_file, 
        maxBytes=5*1024*1024,  # 5MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_fmt = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
    )
    file_handler.setFormatter(file_fmt)
    
    logger.addHandler(console)
    logger.addHandler(file_handler)
    
    logger.info("=" * 80)
    logger.info(f"{name} Logger Initialized")
    logger.info(f"Log File: {os.path.abspath(log_file)}")
    logger.info("=" * 80)
    
    return logger


def log_performance(logger):
    """
    Performance monitoring decorator.
    
    Logs warning if operation takes >500ms.
    
    Usage:
        @log_performance(self.logger)
        def slow_operation(self):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = func(*args, **kwargs)
            elapsed = time.perf_counter() - start
            
            if elapsed > 0.5:  # Log if >500ms
                logger.warning(
                    f"{func.__name__} took {elapsed:.2f}s",
                    extra={
                        'function': func.__name__, 
                        'duration': elapsed,
                        'slow_operation': True
                    }
                )
            else:
                logger.debug(f"{func.__name__} completed in {elapsed:.3f}s")
            
            return result
        return wrapper
    return decorator


def log_operation(logger, operation_name, details=None):
    """
    Log an operation with consistent format.
    
    Args:
        logger: Logger instance
        operation_name: Name of the operation
        details: Optional dictionary of details
    """
    msg = f"OPERATION: {operation_name}"
    if details:
        detail_str = ", ".join(f"{k}={v}" for k, v in details.items())
        msg += f" | {detail_str}"
    logger.info(msg)


def log_validation_error(logger, entity_type, error_message, entity_data=None):
    """
    Log a validation error with structured context.
    
    Args:
        logger: Logger instance
        entity_type: Type of entity (e.g., 'Shipment')
        error_message: Validation error message
        entity_data: Optional entity data for debugging
    """
    logger.warning(
        f"VALIDATION ERROR: {entity_type} - {error_message}",
        extra={
            'error_type': 'validation',
            'entity_type': entity_type,
            'error_message': error_message
        }
    )
    if entity_data:
        logger.debug(f"Entity data: {entity_data}")


def log_data_operation(logger, operation, entity_type, entity_id=None, success=True, error=None):
    """
    Log a data operation (save, load, delete) with structured context.
    
    Args:
        logger: Logger instance
        operation: Operation type ('save', 'load', 'delete')
        entity_type: Type of entity
        entity_id: Optional entity identifier
        success: Whether operation succeeded
        error: Optional error message
    """
    status = "[OK] SUCCESS" if success else "[FAIL] FAILED"
    msg = f"DATA {operation.upper()}: {entity_type}"
    
    if entity_id:
        msg += f" (ID: {entity_id})"
    
    msg += f" - {status}"
    
    extra = {
        'operation': operation,
        'entity_type': entity_type,
        'success': success
    }
    
    if entity_id:
        extra['entity_id'] = entity_id
    
    if success:
        logger.info(msg, extra=extra)
    else:
        logger.error(msg, extra=extra)
        if error:
            logger.error(f"Error details: {error}")


# Example usage
if __name__ == '__main__':
    # Test logging setup
    logger = setup_logger('TestApp', log_dir='../../../logs')
    
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    
    # Test performance decorator
    @log_performance(logger)
    def slow_function():
        time.sleep(0.6)
        return "done"
    
    @log_performance(logger)
    def fast_function():
        time.sleep(0.1)
        return "done"
    
    slow_function()  # Should log warning
    fast_function()  # Should only log debug
    
    log_operation(logger, "test_operation", {"param1": "value1", "param2": 123})
    log_validation_error(logger, "TestEntity", "Invalid field", {"field": "test"})
    log_data_operation(logger, "save", "TestEntity", "test-123", success=True)
    log_data_operation(logger, "load", "TestEntity", error="File not found", success=False)
    
    print("\n[OK] Logging test complete. Check logs/ directory.")
