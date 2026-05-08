import importlib
import logging
import os
from typing import Dict, Any, Type
from core.engines.base_engine import BaseEngine

logger = logging.getLogger(__name__)

class EngineLoader:
    """
    Tiện ích nạp động các file engine cho từng mã sản phẩm.
    """
    ENGINES_DIR = "core/engines"

    @staticmethod
    def get_engine_class(product_id: str) -> Type[BaseEngine]:
        """
        Nạp file Python tương ứng với product_id và trả về class engine.
        File phải được đặt trong core/engines/<product_id>.py
        Class bên trong phải được đặt tên là 'ProductEngine'
        """
        module_path = f"core.engines.{product_id}"
        
        try:
            # Import động module
            module = importlib.import_module(module_path)
            # Reload để đảm bảo lấy code mới nhất nếu có thay đổi (optional)
            importlib.reload(module)
            
            if hasattr(module, "ProductEngine"):
                return getattr(module, "ProductEngine")
            else:
                raise AttributeError(f"Module {module_path} does not have 'ProductEngine' class.")
                
        except ImportError as e:
            logger.error(f"EngineLoader: Could not find engine file for product '{product_id}': {e}")
            raise
        except Exception as e:
            logger.error(f"EngineLoader: Error loading engine for '{product_id}': {e}")
            raise

    @staticmethod
    def create_engine(product_id: str, config: Dict[str, Any]) -> BaseEngine:
        """Khởi tạo một instance của engine."""
        engine_class = EngineLoader.get_engine_class(product_id)
        return engine_class(config)
