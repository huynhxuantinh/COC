import os
import sys
sys.stdout.reconfigure(encoding='utf-8')
from adb_controller import ADBController
from vision import Vision
from logic import BotLogic

def main():
    print("=== Tool Auto Farm COC (Sneaky Goblins) ===")
    
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
    adb = ADBController(device_id="127.0.0.1:5555")
    if not adb.connect():
        print("[!] Không thể kết nối giả lập. Đang thoát...")
        sys.exit(1)
        
    # 2. Khởi tạo Vision
    vision = Vision(template_dir=templates_dir)
    
    # 3. Khởi tạo Logic
    bot_logic = BotLogic(adb, vision)
    
    # Bắt đầu chạy
    try:
        bot_logic.run()
    except KeyboardInterrupt:
        print("\n[*] Đã dừng bot thủ công (Ctrl+C).")

if __name__ == "__main__":
    main()
