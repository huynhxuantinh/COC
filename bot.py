import os
import sys
sys.stdout.reconfigure(encoding='utf-8')
from adb_controller import ADBController
from vision import Vision
from logic import BotLogic

import yaml

def load_config():
    try:
        with open("config/settings.yaml", "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"[!] Lỗi khi đọc file config: {e}")
        return None

def main():
    print("=== Tool Auto Farm COC (Sneaky Goblins) ===")
    
    config = load_config()
    if not config:
        sys.exit(1)
        
    # Tạo thư mục templates nếu chưa có
    templates_dir = "templates"
    if not os.path.exists(templates_dir):
        os.makedirs(templates_dir)
        print(f"[*] Vui lòng chụp các ảnh nút bấm trong game và lưu vào thư mục '{templates_dir}'")
        print("    - attack_btn.png (Nút Attack ở nhà chính)")
        print("    - find_match_btn.png (Nút Tìm trận)")
        print("    - next_btn.png (Nút Next khi đang tìm nhà)")
        print("    - return_home_btn.png (Nút Return Home sau khi đánh xong)")
        print("    - sneaky_goblin_card.png (Icon thẻ lính Sneaky Goblin)")
    
    # 1. Khởi tạo ADB
    device_id = config.get("emulator", {}).get("device_id", "127.0.0.1:5555")
    adb_path = config.get("emulator", {}).get("adb_path", None)
    adb = ADBController(device_id=device_id, adb_path=adb_path)
    if not adb.connect():
        print("[!] Không thể kết nối giả lập. Đang thoát...")
        sys.exit(1)
        
    # 2. Khởi tạo Vision
    vision = Vision(template_dir=templates_dir, config=config)
    
    # 3. Khởi tạo Logic
    bot_logic = BotLogic(adb, vision, config)
    
    # Bắt đầu chạy
    try:
        bot_logic.run()
    except KeyboardInterrupt:
        print("\n[*] Đã dừng bot thủ công (Ctrl+C).")

if __name__ == "__main__":
    main()
