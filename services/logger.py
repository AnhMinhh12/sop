import logging
from logging.handlers import RotatingFileHandler
import os
from services.config_loader import ConfigLoader

def setup_logger():
    """
    Sets up the global logger based on config settings.
    """
    # Load config (đã được nạp ở main hoặc bước trước)
    log_file = ConfigLoader.get('logging.log_file', 'data/logs/system.log')
    log_level_str = ConfigLoader.get('logging.level', 'INFO').upper()
    max_mb = ConfigLoader.get('logging.max_log_mb', 100)
    
    # Chuyển đổi level string sang logging constant
    level = getattr(logging, log_level_str, logging.INFO)
    
    # Tạo thư mục log nếu chưa có
    log_dir = os.path.dirname(log_file)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    # Format log
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    formatter = logging.Formatter(log_format)
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Clear existing handlers
    if root_logger.hasHandlers():
        root_logger.handlers.clear()
        
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (Rotating)
    file_handler = RotatingFileHandler(
        log_file, 
        maxBytes=max_mb * 1024 * 1024, 
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    logging.info(f"Logger initialized. Level: {log_level_str}, File: {log_file}")

# Khởi tạo mặc định nếu module được import
if __name__ == "__main__":
    # Test logger
    setup_logger()
    logging.info("Test log message.")
