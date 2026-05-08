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
    def update(self, hands_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Xử lý dữ liệu tay từ frame hiện tại.
        Trả về dictionary chứa trạng thái SOP (step_index, status_msg, v.v.)
        """
        pass

    @abstractmethod
    def reset(self) -> None:
        """Reset trạng thái chu kỳ về ban đầu."""
        pass

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """Lấy trạng thái hiện tại của engine."""
        pass
