import time
import random

class BotLogic:
    def __init__(self, adb, vision, config=None):
        self.adb = adb
        self.vision = vision
        self.config = config or {}
        
        self.state = "IDLE"
        self.idle_stuck_count = 0
        self.search_stuck_count = 0
        
        # Đọc ngưỡng farm từ config
        loot_config = self.config.get("farm", {}).get("loot_threshold", {})
        self.target_gold = loot_config.get("gold", 700000)
        self.target_elixir = loot_config.get("elixir", 700000)
        
        # Region dự kiến cho số vàng và dầu (cần điều chỉnh lại theo độ phân giải màn hình)
        # Tương lai có thể tính toán từ resolution trong config
        self.gold_region = (120, 130, 150, 40)
        self.elixir_region = (120, 190, 150, 40)

    def run(self):
        """Vòng lặp chính của Bot."""
        print(f"Bắt đầu khởi chạy Bot... Mục tiêu: Vàng > {self.target_gold}, Dầu > {self.target_elixir}")
        while True:
            try:
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
            except Exception as e:
                print(f"[!] LỖI NGHIÊM TRỌNG (Watchdog caught): {e}")
                print("[!] Bot sẽ reset lại state về IDLE và thử lại sau 3 giây...")
                self.state = "IDLE"
                time.sleep(3)

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
                print("[IDLE] Bấm nút X hoặc thoát để thử đóng menu ẩn.")
                close_btn = self.vision.find_template(screen, "close_btn.png")
                if close_btn:
                    self.adb.click(close_btn[0], close_btn[1])
                else:
                    self.adb.click(1850, 80) # Fallback tọa độ cứng
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
            self.search_stuck_count = 0
            print(f"[SEARCHING] Đạt chỉ tiêu (>700k)! Bắt đầu tấn công.")
            self.state = "ATTACKING"
        else:
            if gold == 0 and elixir == 0:
                self.search_stuck_count += 1
                print(f"[SEARCHING] Đang tải mây... chờ thêm ({self.search_stuck_count}/15).")
                if self.search_stuck_count >= 15:
                    print("[SEARCHING] Kẹt quá lâu! Bấm X nhiều lần để thoát các menu ẩn...")
                    close_btn = self.vision.find_template(screen, "close_btn.png")
                    cx, cy = close_btn if close_btn else (1850, 80)
                    self.adb.click(cx, cy)
                    time.sleep(1)
                    self.adb.click(cx, cy)
                    time.sleep(2)
                    self.state = "IDLE"
                    self.search_stuck_count = 0
                else:
                    time.sleep(2)
            else:
                self.search_stuck_count = 0
                print("[SEARCHING] Nghèo quá, Next!")
                next_btn = self.vision.find_template(screen, "next_btn.png")
                if next_btn:
                    self.adb.click(next_btn[0], next_btn[1])
                else:
                    # Fallback tọa độ cứng
                    self.adb.click(1750, 800)
                time.sleep(3) # Chờ load mây

    def deploy_sneaky_goblins(self, screen):
        """Chiến thuật thả Sneaky Goblins."""
        print("[ATTACKING] Đang triển khai Sneaky Goblins...")
        # Ở cấp độ cơ bản, bot sẽ thả một vòng quanh map để Goblins tự chạy vào các mỏ ngoài
        # Màn hình game thường là vùng trung tâm. Ta vẽ 1 hình chữ nhật lớn để click
        # Phải chọn đúng icon Sneaky Goblins trước khi thả
        
        # 1. Tìm thẻ lính Sneaky Goblin
        goblin_card = self.vision.find_template(screen, "sneaky_goblin_card.png")
        if goblin_card:
            self.adb.click(goblin_card[0], goblin_card[1])
        else:
            print("[ATTACKING] Không tìm thấy ảnh thẻ lính, dùng tọa độ dự phòng (200, 950)")
            self.adb.click(200, 950)
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
        
        # Đánh xong, đợi kết thúc trận linh hoạt
        print("[ATTACKING] Đang tấn công... Chờ trận đấu kết thúc.")
        max_wait = 60  # Đợi tối đa 60 giây
        for i in range(max_wait // 2):
            time.sleep(2)
            curr_screen = self.adb.screencap()
            if curr_screen is None:
                continue
                
            return_home = self.vision.find_template(curr_screen, "return_home_btn.png")
            if return_home:
                print(f"[ATTACKING] Phát hiện nút Về Nhà tại {return_home}. Trận đấu đã xong!")
                self.adb.click(return_home[0], return_home[1])
                time.sleep(6) # Chờ load về nhà
                self.state = "IDLE"
                return
                
            print(f"[ATTACKING] Vẫn đang đánh... ({i*2}/{max_wait}s)")
            
        print("[ATTACKING] Timeout 60s. Bấm Về Nhà dự phòng.")
        fallback_return_btn = self.vision.find_template(curr_screen, "return_home_btn.png") if curr_screen is not None else None
        if fallback_return_btn:
            self.adb.click(fallback_return_btn[0], fallback_return_btn[1])
        else:
            # Tọa độ cứng fallback theo màn 1920x1080
            h, w = screen.shape[:-1]
            self.adb.click(w // 2, h - 130)
        time.sleep(6)
        self.state = "IDLE"
