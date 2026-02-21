import logging

def setup_logger(name: str = None, level: int = logging.INFO) -> logging.Logger:
    """Set up a logger with basic configuration.
    
    Args:
        name: Name for the logger. If None, uses the root logger
        level: Logging level to use
        
    Returns:
        The configured logger
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Create console handler with formatting
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(level)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger 