import os
import sys
import io
import requests
import time
import json
import shutil
import re
from datetime import datetime
from dotenv import load_dotenv

# Fix UnicodeEncodeError on Windows terminal
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def sync_ui():
    """
    Script đồng bộ giao diện (UI) từ AI Monitoring Hub.
    Phiên bản 4.0: Linh hoạt cấu trúc thư mục, hỗ trợ Offline Mode & Path Mapping.
    """
    print("\n" + "="*60)
    print("   AI MONITORING HUB - UI SYNCHRONIZER (VERSION 4.0)")
    print("="*60)
    
    # 1. Load cấu hình
    load_dotenv()
    hub_url = os.getenv("HUB_URL")
    
    if not hub_url:
        print("\n[!] Lỗi: Không tìm thấy HUB_URL trong file .env")
        print("    Vui lòng thêm HUB_URL=http://<ip-cua-hub>:4000 vào .env")
        return

    hub_url = hub_url.rstrip('/')
    cache_buster = int(time.time())
    
    # 2. Lấy Manifest từ Hub
    print(f"\n[*] Đang kết nối tới Hub: {hub_url}...")
    try:
        manifest_url = f"{hub_url}/api/shared/manifest?t={cache_buster}"
        response = requests.get(manifest_url, timeout=10)
        if response.status_code != 200:
            print(f"[!] Không thể lấy manifest từ Hub (HTTP {response.status_code})")
            return
        hub_manifest = response.json()
    except Exception as e:
        print(f"[X] Lỗi kết nối tới Hub: {e}")
        return

    hub_version = hub_manifest.get("version", "unknown")
    print(f"[OK] Đã tìm thấy UI Version: {hub_version}")

    # 3. Cấu hình linh hoạt cho dự án vệ tinh
    # Tự động phát hiện cấu trúc thư mục
    use_app_dir = os.path.exists(os.path.join(os.getcwd(), 'app'))
    path_mapping = {}
    
    if not use_app_dir:
        print("[!] Phát hiện cấu trúc thư mục phẳng (Flat Structure). Tự động ánh xạ đường dẫn...")
        path_mapping = {
            'app/templates/': 'templates/',
            'app/static/': 'static/'
        }

    offline_mode = input("\n[?] Bạn có muốn sử dụng chế độ Offline? (Gỡ bỏ tiền tố HUB_URL trong code) (y/n): ").lower() == 'y'

    # 4. Bắt đầu đồng bộ
    files_to_sync = hub_manifest.get("files", {})
    success_count = 0
    total_files = len(files_to_sync)
    
    print(f"\n[1/1] Đang đồng bộ {total_files} tệp giao diện...")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = os.path.join(os.getcwd(), 'backups', f'ui_{timestamp}')
    
    for hub_path, local_path in files_to_sync.items():
        # Ánh xạ đường dẫn nếu cần
        final_local_path = local_path
        for old_prefix, new_prefix in path_mapping.items():
            if final_local_path.startswith(old_prefix):
                final_local_path = final_local_path.replace(old_prefix, new_prefix, 1)

        # Phân loại URL
        if hub_path.startswith('templates/'):
            template_name = hub_path.replace('templates/', '')
            url = f"{hub_url}/api/shared/templates/{template_name}?t={cache_buster}"
        else:
            url = f"{hub_url}/{hub_path}?t={cache_buster}"
            
        if download_and_process_file(url, final_local_path, backup_root, offline_mode):
            success_count += 1

    # 5. Lưu manifest local
    if success_count == total_files:
        local_manifest_path = os.path.join(os.getcwd(), 'ui_manifest.local.json')
        with open(local_manifest_path, 'w', encoding='utf-8') as f:
            json.dump(hub_manifest, f, indent=4)
        print(f"\n[OK] Đã cập nhật manifest local sang phiên bản {hub_version}")

    print("\n" + "="*60)
    print(f" HOÀN TẤT: Đã đồng bộ {success_count}/{total_files} tệp thành công!")
    print(f" BACKUP: Các tệp cũ đã được lưu tại: {backup_root}")
    print("="*60)
    print("Ghi chú: ")
    print("- Vui lòng khởi động lại Flask server để thấy thay đổi mới nhất.\n")

def download_and_process_file(url, local_path, backup_root, offline_mode):
    """Tải, backup và xử lý file (nếu cần chế độ Offline)."""
    save_path = os.path.join(os.getcwd(), local_path)
    
    if os.path.exists(save_path):
        backup_path = os.path.join(backup_root, local_path)
        os.makedirs(os.path.dirname(backup_path), exist_ok=True)
        shutil.copy2(save_path, backup_path)
    
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0 UI-Sync-Tool/4.0'}
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            is_binary = any(ext in local_path for ext in ['.png', '.jpg', '.ico', '.woff'])
            mode = 'wb' if is_binary else 'w'
            encoding = 'utf-8' if mode == 'w' else None
            
            content = response.text if mode == 'w' else response.content
            
            # Xử lý Offline Mode: Xóa bỏ tiền tố {{ config.HUB_URL }}
            if offline_mode and not is_binary and (local_path.endswith('.html') or local_path.endswith('.js')):
                # Tìm và xóa các tiền tố HUB_URL trong template
                content = content.replace('{{ config.HUB_URL }}', '')
                # Xử lý cả các trường hợp config['HUB_URL']
                content = content.replace("{{ config['HUB_URL'] }}", "")
            
            with open(save_path, mode, encoding=encoding) as f:
                f.write(content)
                
            print(f"  [OK] {local_path}")
            return True
        else:
            print(f"  [!] Lỗi tải {local_path}: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"  [X] Không thể tải {local_path}: {str(e)}")
        return False

if __name__ == "__main__":
    try:
        sync_ui()
    except KeyboardInterrupt:
        print("\n\n[!] Đã dừng script bởi người dùng.")
        sys.exit(0)
