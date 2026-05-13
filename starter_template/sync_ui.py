import os
import requests
from dotenv import load_dotenv

def sync_templates():
    print("=== Bắt đầu đồng bộ giao diện từ Hub Server ===")
    
    # Load cấu hình từ file .env (nếu chưa có .env thì dùng .env.example làm mẫu)
    if not os.path.exists('.env') and os.path.exists('.env.example'):
        print("Thông báo: Đang tạo file .env từ .env.example...")
        with open('.env.example', 'r', encoding='utf-8') as fsrc:
            with open('.env', 'w', encoding='utf-8') as fdst:
                fdst.write(fsrc.read())

    load_dotenv()
    hub_url = os.getenv("HUB_URL")
    
    if not hub_url:
        print("Lỗi: Không tìm thấy HUB_URL trong file .env")
        return

    # Danh sách các file cần đồng bộ từ Hub
    templates_to_sync = [
        'base.html',
        'partials/sidebar.html',
        'partials/header.html',
        'partials/modals.html'
    ]
    
    templates_dir = os.path.join(os.path.dirname(__file__), 'app', 'templates')
    os.makedirs(os.path.join(templates_dir, 'partials'), exist_ok=True)
    
    success_count = 0
    for tmpl in templates_to_sync:
        url = f"{hub_url.rstrip('/')}/api/shared/templates/{tmpl}"
        save_path = os.path.join(templates_dir, tmpl)
        
        try:
            print(f"Đang tải {tmpl} từ {url}...")
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                with open(save_path, 'w', encoding='utf-8') as f:
                    f.write(response.text)
                print(f"  -> Đã cập nhật thành công: {tmpl}")
                success_count += 1
            else:
                print(f"  -> Lỗi tải {tmpl}: {response.status_code}")
        except Exception as e:
            print(f"  -> Không thể kết nối đến Hub Server: {e}")
            
    print(f"=== Đồng bộ hoàn tất: {success_count}/{len(templates_to_sync)} file ===")

if __name__ == "__main__":
    sync_templates()
