import time
import random

class BotLogic:
    def __init__(self, adb, vision):
        self.adb = adb
        self.vision = vision
        self.state = "IDLE"
        self.idle_stuck_count = 0
        self.target_gold = 700000
        self.target_elixir = 700000
        
        # Region dự kiến cho số vàng và dầu (cần điều chỉnh lại theo độ phân giải màn hình)
        # Giả sử LDPlayer đang ở độ phân giải 1600x900
        self.gold_region = (120, 130, 150, 40)   # Ví dụ: X, Y, Width, Height
        self.elixir_region = (120, 190, 150, 40)

    def run(self):
        """Vòng lặp chính của Bot."""
        print("Bắt đầu khởi chạy Bot...")
        while True:
            screen = self.adb.screencap()
            if screen is None:
                print("Lỗi chụp màn hình. Đang thử lại...")
                time.sleep(2)
                continue

            if self.state == "IDLE":
                self.handle_idle(screen)
            elif self.state == "SEARCHING":
                self.handle_searching(screen)
            elif self.state == "ATTACKING":
                self.handle_attacking(screen)
            
            time.sleep(1) # Chờ 1 giây giữa các chu kỳ

    def handle_idle(self, screen):
        """Xử lý khi ở nhà chính."""
        print("[IDLE] Đang ở nhà chính.")
        # Kiểm tra nút Attack (Attack.png)
        attack_btn = self.vision.find_template(screen, "attack_btn.png")
        if attack_btn:
            self.idle_stuck_count = 0
            print("[IDLE] Tìm thấy nút Tấn công. Chuẩn bị đi farm...")
            self.adb.click(attack_btn[0], attack_btn[1])
            time.sleep(2) # Chờ menu tấn công hiện lên
            
            self.state = "SEARCHING"
        else:
            self.idle_stuck_count += 1
            print(f"[IDLE] Không thấy nút Tấn công ({self.idle_stuck_count}/3). Có thể đang mở menu khác...")
            if self.idle_stuck_count >= 3:
                print("[IDLE] Bấm nút X (1850, 80) hoặc thoát để thử đóng menu.")
                self.adb.click(1850, 80)
                time.sleep(1)
                self.idle_stuck_count = 0

    def handle_searching(self, screen):
        """Xử lý quá trình tìm nhà (Next liên tục)."""
        # Tìm nút Find a Match nếu đang ở menu Attack
        find_match_btn = self.vision.find_template(screen, "find_match_btn.png")
        if find_match_btn:
            print("[SEARCHING] Đang bấm Tìm trận...")
            self.adb.click(find_match_btn[0], find_match_btn[1])
            time.sleep(4) # Chờ load mây
            return

        # Hardcode vị trí nút Next (độ phân giải 1920x1080)
        next_btn = (1750, 800)
        
        print("[SEARCHING] Đang soi tài nguyên...")
        # Đọc tài nguyên
        gold = self.vision.read_resources(screen, self.gold_region)
        elixir = self.vision.read_resources(screen, self.elixir_region)
        print(f"[SEARCHING] Vàng: {gold} | Tiên dược: {elixir}")

        if gold >= self.target_gold or elixir >= self.target_elixir:
            print(f"[SEARCHING] Đạt chỉ tiêu (>700k)! Bắt đầu tấn công.")
            self.state = "ATTACKING"
        else:
            if gold == 0 and elixir == 0:
                print("[SEARCHING] Đang tải mây... chờ thêm.")
                time.sleep(2)
            else:
                print("[SEARCHING] Nghèo quá, Next!")
                self.adb.click(next_btn[0], next_btn[1])
                time.sleep(3) # Chờ load mây

    def deploy_sneaky_goblins(self, screen):
        """Chiến thuật thả Sneaky Goblins."""
        print("[ATTACKING] Đang triển khai Sneaky Goblins...")
        # Ở cấp độ cơ bản, bot sẽ thả một vòng quanh map để Goblins tự chạy vào các mỏ ngoài
        # Màn hình game thường là vùng trung tâm. Ta vẽ 1 hình chữ nhật lớn để click
        # Phải chọn đúng icon Sneaky Goblins trước khi thả
        
        # 1. Hardcode tọa độ thẻ lính đầu tiên (Sneaky Goblin)
        goblin_card = (200, 950)
        self.adb.click(goblin_card[0], goblin_card[1])
        time.sleep(0.5)

        # 2. Thả lính quanh viền
        # Cần xác định tọa độ biên (margins) của màn hình LDPlayer
        margin = 150
        # Cần width, height từ screen.shape
        h, w = screen.shape[:-1]
        
        # Thả 10 con ngẫu nhiên ở viền
        for _ in range(10):
            # Chọn ngẫu nhiên cạnh trên, dưới, trái, phải
            side = random.choice(["top", "bottom", "left", "right"])
            if side == "top":
                tx, ty = random.randint(margin, w - margin), margin
            elif side == "bottom":
                tx, ty = random.randint(margin, w - margin), h - margin
            elif side == "left":
                tx, ty = margin, random.randint(margin, h - margin)
            else: # right
                tx, ty = w - margin, random.randint(margin, h - margin)
            
            self.adb.click(tx, ty)
            time.sleep(0.2)

    def handle_attacking(self, screen):
        """Xử lý quá trình đánh."""
        # Gọi chiến thuật thả lính
        self.deploy_sneaky_goblins(screen)
        
        # Đánh xong, chờ 35 giây rồi bấm Return Home (tọa độ cứng)
        print("[ATTACKING] Đang tấn công... Chờ 35 giây.")
        time.sleep(35)
        print("[ATTACKING] Trận đấu kết thúc. Bấm Về Nhà.")
        self.adb.click(960, 950)
        time.sleep(6) # Chờ load về nhà
        self.state = "IDLE"
