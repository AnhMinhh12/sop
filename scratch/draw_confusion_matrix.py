import os
import sys

def generate_matrix():
    try:
        import matplotlib
        # Sử dụng Agg backend để tránh lỗi GUI trên Windows Server nếu chạy headless
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import numpy as np
        
        # Thiết lập font hiển thị tiếng Việt đẹp
        plt.rcParams['font.sans-serif'] = 'Arial'
        plt.rcParams['font.family'] = 'sans-serif'
        
        # Số liệu mới
        # TP = 1168, FP = 13, FN = 7, TN = 1251
        matrix = np.array([[1168, 13], 
                           [7, 1251]])
        
        fig, ax = plt.subplots(figsize=(10, 6.5), dpi=300)
        fig.patch.set_facecolor('white')
        ax.set_facecolor('white')
        
        # Màu sắc: Xanh lá cho đúng, Hồng nhạt/Cam nhạt cho sai
        # Tạo bản đồ màu tùy chỉnh
        colors = [['#5cb85c', '#fce8e6'], 
                  ['#fce8e6', '#5cb85c']]
        
        # Vẽ các ô vuông thủ công để có màu sắc chính xác tuyệt đối như hình vẽ của user
        for i in range(2):
            for j in range(2):
                color = colors[i][j]
                rect = plt.Rectangle((j - 0.45, 1 - i - 0.45), 0.9, 0.9, facecolor=color, edgecolor='white', linewidth=3)
                ax.add_patch(rect)
                
                # Điền chữ số vào giữa ô
                val = matrix[i][j]
                text_color = 'white' if color == '#5cb85c' else '#c9302c'
                ax.text(j, 1 - i, f"{val:,}".replace(",", "."), ha='center', va='center', 
                        fontsize=28, fontweight='bold', color=text_color)
        
        # Thiết lập nhãn trục X (ở phía trên của biểu đồ)
        ax.text(0, 1.6, "Đúng quy trình", ha='center', va='center', fontsize=12, fontweight='bold', color='#333333')
        ax.text(1, 1.6, "Vi phạm", ha='center', va='center', fontsize=12, fontweight='bold', color='#333333')
        
        # Thiết lập nhãn trục Y (ở phía bên trái của biểu đồ)
        ax.text(-0.7, 1, "Đúng quy trình", ha='right', va='center', fontsize=12, fontweight='bold', color='#333333')
        ax.text(-0.7, 0, "Vi phạm", ha='right', va='center', fontsize=12, fontweight='bold', color='#333333')
        
        # Tiêu đề biểu đồ
        ax.text(0.5, 1.9, "Ma trận nhầm lẫn kiểm duyệt chu kỳ SOP", ha='center', va='center', 
                fontsize=18, fontweight='bold', color='#0f4c81')
        
        # Vẽ khung văn bản thông số bên phải
        info_text = (
            "Precision: 98.90%\n"
            "Recall: 99.40%\n"
            "F1-Score: 99.15%"
        )
        ax.text(1.65, 0.5, info_text, ha='left', va='center', fontsize=16, fontweight='bold', 
                color='#1e427b', linespacing=1.6)
        
        # Cấu hình hệ trục tọa độ để ẩn các đường biên cũ
        ax.set_xlim(-1.2, 2.7)
        ax.set_ylim(-0.6, 2.1)
        ax.axis('off')
        
        plt.tight_layout()
        
        # Đảm bảo thư mục images tồn tại
        os.makedirs("images", exist_ok=True)
        
        output_path = "images/figure_4_7.png"
        plt.savefig(output_path, bbox_inches='tight', facecolor='white', dpi=300)
        plt.close()
        print(f"SUCCESS: Generated confusion matrix plot at {output_path}")
        return True
        
    except ImportError:
        print("Matplotlib not installed. Installing matplotlib...")
        return False

if __name__ == "__main__":
    success = generate_matrix()
    if not success:
        sys.exit(1)
    else:
        sys.exit(0)
