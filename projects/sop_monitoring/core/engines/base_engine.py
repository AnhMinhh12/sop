import os
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional

class BaseEngine(ABC):
    """
    Lớp cơ sở trừu tượng cho tất cả các Engine logic của từng mã sản phẩm.
    Mỗi mã sản phẩm mới sẽ tạo 1 file Python kế thừa lớp này.
    """
    
    @abstractmethod
    def __init__(self, config: Dict[str, Any]):
        """Khởi tạo engine với cấu hình (vùng, bước, tham số)."""
        pass

    @abstractmethod
    def update(self, hands_data: List[Dict]) -> Dict[str, Any]:
        """Xử lý dữ liệu bàn tay và trả về trạng thái SOP."""
        pass

    def log_debug(self, message: str, product_id: str):
        """Ghi log chi tiết cho từng mã sản phẩm vào file riêng."""
        log_dir = "data/logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        log_path = os.path.join(log_dir, f"{product_id}_debug.txt")
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        
        try:
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(f"[{timestamp}] {message}\n")
        except Exception as e:
            print(f"Error writing debug log: {e}")

    @abstractmethod
    def reset(self) -> None:
        """Reset trạng thái engine."""
        pass

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """Lấy trạng thái hiện tại của engine."""
        pass
