import os
import time
import cv2
import numpy as np
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
    def update(self, hands_data: List[Dict], products_data: List[Dict] = None,
                robot_data: List[Dict] = None) -> Dict[str, Any]:
        """Xử lý dữ liệu bàn tay, sản phẩm, và robot, trả về trạng thái SOP."""
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

    # --- Helper methods có thể tái sử dụng giữa các engine ---

    def _select_nearest_hands(self, hands_data: List[Dict], zone_name: str,
                               n: int = 2) -> set:
        """
        Chọn n tay gần zone nhất (theo khoảng cách centroid → polygon).
        Trả về set các side ('left', 'right') của các tay được chọn.
        Fallback: nếu zone không tồn tại, dùng tất cả hands có sẵn.
        """
        zones = getattr(self, 'zones', {})
        zone_pts = zones.get(zone_name)
        if not zone_pts:
            return set()

        poly = np.array(zone_pts, dtype=np.float32)
        w, h = self.config.get("w", 640), self.config.get("h", 480)
        dists = []
        for hand in hands_data:
            cx, cy = hand["centroid"]
            # pointPolygonTest signed distance: âm = ngoài, dương = trong
            d = abs(cv2.pointPolygonTest(poly, (cx, cy), True))
            dists.append((d, hand["label"].lower()))
        dists.sort(key=lambda x: x[0])

        available_sides = set(h["label"].lower() for h in hands_data)
        selected = set()
        for d, side in dists:
            if len(selected) >= n:
                break
            if side in available_sides and side not in selected:
                selected.add(side)
        return selected

    def _is_object_in_zone(self, objects: List[Dict], zone_name: str,
                           centroid_only: bool = False) -> bool:
        """
        Kiểm tra xem có object nào (robot, product, ...) trong zone không.
        Dùng chung cho robot và product.
        """
        zone_pts = getattr(self, 'zones', {}).get(zone_name)
        if not zone_pts:
            return False
        poly = np.array(zone_pts, dtype=np.float32)
        w, h = self.config.get("w", 640), self.config.get("h", 480)
        for obj in objects:
            centroid = obj.get("centroid")
            if not centroid:
                bbox = obj.get("bbox", [])
                if len(bbox) >= 4:
                    centroid = [(bbox[0] + bbox[2]) / 2 / w, (bbox[1] + bbox[3]) / 2 / h]
            if not centroid:
                continue
            test_points = [centroid]
            if not centroid_only:
                bbox = obj.get("bbox", [])
                if len(bbox) >= 4:
                    test_points = [
                        centroid,
                        [bbox[0] / w, bbox[1] / h],
                        [bbox[2] / w, bbox[1] / h],
                        [bbox[0] / w, bbox[3] / h],
                        [bbox[2] / w, bbox[3] / h],
                    ]
            if any(cv2.pointPolygonTest(poly, (p[0], p[1]), False) >= 0 for p in test_points):
                return True
        return False

    def _check_bbox_polygon_intersection(self, bbox: List[float], poly_pts: List[List[float]], 
                                         centroid: List[float], w: int, h: int, 
                                         centroid_only: bool = False) -> bool:
        """
        Kiểm tra xem bounding box của bàn tay có giao cắt (chạm) với vùng đa giác không.
        Nếu centroid_only=True, chỉ kiểm tra centroid.
        Ngược lại, kiểm tra:
        1. Centroid trong đa giác.
        2. Bất kỳ góc nào của bbox trong đa giác.
        3. Bất kỳ đỉnh nào của đa giác trong bbox.
        4. Bất kỳ cạnh nào của bbox giao cắt với cạnh của đa giác.
        """
        poly = np.array(poly_pts, np.float32)
        
        # 1. Check centroid
        if cv2.pointPolygonTest(poly, (centroid[0], centroid[1]), False) >= 0:
            return True
        if centroid_only:
            return False
            
        # Tọa độ bbox chuẩn hóa
        xmin, ymin, xmax, ymax = bbox[0] / w, bbox[1] / h, bbox[2] / w, bbox[3] / h
        corners = [
            [xmin, ymin],
            [xmax, ymin],
            [xmax, ymax],
            [xmin, ymax]
        ]
        
        # 2. Check if any bbox corner is inside the polygon
        for c in corners:
            if cv2.pointPolygonTest(poly, (c[0], c[1]), False) >= 0:
                return True
                
        # 3. Check if any polygon vertex is inside the bbox
        for pt in poly_pts:
            if xmin <= pt[0] <= xmax and ymin <= pt[1] <= ymax:
                return True
                
        # 4. Check if any edge of the bbox intersects any edge of the polygon
        def ccw(A, B, C):
            return (C[1] - A[1]) * (B[0] - A[0]) > (B[1] - A[1]) * (C[0] - A[0])
            
        def intersect(A, B, C, D):
            return ccw(A, C, D) != ccw(B, C, D) and ccw(A, B, C) != ccw(A, B, D)
            
        bbox_edges = [
            (corners[0], corners[1]),
            (corners[1], corners[2]),
            (corners[2], corners[3]),
            (corners[3], corners[0])
        ]
        
        n_poly = len(poly_pts)
        poly_edges = []
        for i in range(n_poly):
            poly_edges.append((poly_pts[i], poly_pts[(i + 1) % n_poly]))
            
        for b_edge in bbox_edges:
            for p_edge in poly_edges:
                if intersect(b_edge[0], b_edge[1], p_edge[0], p_edge[1]):
                    return True
                    
        return False

