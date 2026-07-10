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
        farm_config = self.config.get("farm", {})
        loot_config = farm_config.get("loot_threshold", {})
        self.target_gold = loot_config.get("gold", 700000)
        self.target_elixir = loot_config.get("elixir", 700000)
        
        # Cấu hình rải quân
        self.troops = farm_config.get("troops", [])
        if not self.troops:
            # Fallback nếu config thiếu
            self.troops = [{
                "name": "sneaky_goblin",
                "template": "sneaky_goblin_card.png",
                "count": 15,
                "pattern": "perimeter"
            }]
        
        # Region dự kiến cho số vàng và dầu (rộng hơn để đọc được số hàng triệu)
        self.gold_region = (135, 130, 250, 40)
        self.elixir_region = (135, 190, 250, 40)
        
        # Thống kê farm
        self.stats = {"attacks": 0, "gold": 0, "elixir": 0}

    def run(self):
        """Vòng lặp chính của Bot."""
        print(f"Bắt đầu khởi chạy Bot... Mục tiêu: Vàng > {self.target_gold}, Dầu > {self.target_elixir}")
        
        # Đọc cấu hình an toàn
        safety_config = self.config.get("safety", {})
        session_hours = safety_config.get("session_hours", 2)
        break_minutes = safety_config.get("break_minutes", 30)
        
        start_time = time.time()
        
        while True:
            # Kiểm tra thời gian chơi (chống ban)
            elapsed_sec = time.time() - start_time
            if session_hours > 0 and elapsed_sec > (session_hours * 3600):
                print(f"[*] Đã cày cuốc liên tục {session_hours} giờ. Bắt đầu nghỉ giải lao {break_minutes} phút...")
                time.sleep(break_minutes * 60)
                print("[*] Đã nghỉ xong! Tiếp tục farm nào...")
                start_time = time.time() # Reset lại mốc thời gian

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
        
        # 1. Ưu tiên kiểm tra nút Attack xanh lá (nếu đang lỡ bị kẹt ở My Army từ trước)
        force_attack = self.vision.find_template(screen, "force_attack_btn.png")
        if force_attack:
            self.idle_stuck_count = 0
            print("[IDLE] Đang ở màn hình My Army. Bấm nút Attack xanh lá để bắt đầu tìm nhà...")
            self.adb.click(force_attack[0], force_attack[1])
            time.sleep(3)
            self.state = "SEARCHING"
            return
            
        # 2. Kiểm tra nút Attack bình thường (Attack.png)
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
            self.stats["attacks"] += 1
            self.stats["gold"] += gold
            self.stats["elixir"] += elixir
            print(f"[*] THỐNG KÊ: Đã đánh {self.stats['attacks']} trận | Cướp được: {self.stats['gold']:,} Vàng, {self.stats['elixir']:,} Dầu")
            self.search_stuck_count = 0
            print(f"[SEARCHING] Đạt chỉ tiêu (Vàng>{self.target_gold} hoặc Dầu>{self.target_elixir})! Bắt đầu tấn công.")
            self.state = "ATTACKING"
        else:
            if gold == 0 and elixir == 0:
                # Kiểm tra xem có đang bị kẹt ở màn hình My Army (do cảnh báo Hero đang hồi máu) không
                goblin_card = self.vision.find_template(screen, "sneaky_goblin_card.png")
                force_attack = self.vision.find_template(screen, "force_attack_btn.png")
                
                if force_attack or goblin_card:
                    print("[SEARCHING] Bị vướng màn hình My Army. Bấm nút Attack xanh lá...")
                    # Nút Attack ở góc dưới bên phải, tọa độ chuẩn xác là quanh (1750, 940)
                    if force_attack:
                        self.adb.click(force_attack[0], force_attack[1])
                    else:
                        self.adb.click(1750, 940)
                    time.sleep(3)
                else:
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

    def get_perimeter_points(self, w, h, n, margin):
        """Trả về n tọa độ phân bố đều quanh viền màn hình (hình chữ nhật)."""
        points = []
        top_w = w - 2 * margin
        side_h = h - 2 * margin
        perimeter = 2 * top_w + 2 * side_h
        
        for i in range(n):
            d = (i * perimeter / n) + random.uniform(-10, 10)
            d = d % perimeter
            if d < top_w: # Cạnh trên
                points.append((margin + d, margin))
            elif d < top_w + side_h: # Cạnh phải
                points.append((w - margin, margin + (d - top_w)))
            elif d < 2 * top_w + side_h: # Cạnh dưới
                points.append((w - margin - (d - (top_w + side_h)), h - margin))
            else: # Cạnh trái
                points.append((margin, h - margin - (d - (2 * top_w + side_h))))
                
        return [(int(x), int(y)) for x, y in points]

    def get_edge_cluster_points(self, w, h, n, margin):
        """Trả về n tọa độ dồn vào một cạnh ngẫu nhiên."""
        points = []
        side = random.choice(["top", "bottom", "left", "right"])
        for _ in range(n):
            if side == "top":
                tx, ty = random.randint(margin, w - margin), margin
            elif side == "bottom":
                tx, ty = random.randint(margin, w - margin), h - margin
            elif side == "left":
                tx, ty = margin, random.randint(margin, h - margin)
            else: # right
                tx, ty = w - margin, random.randint(margin, h - margin)
            points.append((tx, ty))
        return points

    def deploy_troops(self, screen):
        """Thả quân dựa trên config farm.troops."""
        h, w = screen.shape[:-1]
        margin = 150
        
        delay_min = self.config.get("battle", {}).get("deploy_delay_min", 0.15)
        delay_max = self.config.get("battle", {}).get("deploy_delay_max", 0.4)
        offset = self.config.get("farm", {}).get("troop_count_offset", [-45, -55, 10, -20])
        
        print("[ATTACKING] Đang triển khai quân đội...")
        
        for troop in self.troops:
            name = troop.get("name", "Unknown")
            template = troop.get("template")
            default_count = troop.get("count", 0)
            pattern = troop.get("pattern", "perimeter")
            
            print(f"[ATTACKING] Chuẩn bị thả {name}...")
            card_loc = self.vision.find_template(screen, template)
            if not card_loc:
                print(f"[ATTACKING] Không tìm thấy thẻ quân {name}. Bỏ qua.")
                continue
                
            # Click chọn thẻ quân
            self.adb.click(card_loc[0], card_loc[1])
            time.sleep(0.5)
            
            # Đọc số lượng còn lại
            count = self.vision.read_troop_count(screen, card_loc, offset)
            if count == -1:
                print(f"[ATTACKING] OCR không đọc được số lượng {name}, dùng mặc định: {default_count}")
                count = default_count
            elif count == 0:
                print(f"[ATTACKING] Hết quân {name}.")
                continue
                
            if count <= 0:
                continue
                
            print(f"[ATTACKING] Sẽ thả {count} {name} theo pattern '{pattern}'")
            
            # Tính toán danh sách điểm
            if pattern == "edge_cluster":
                points = self.get_edge_cluster_points(w, h, count, margin)
            else:
                points = self.get_perimeter_points(w, h, count, margin)
                
            for i, (tx, ty) in enumerate(points):
                # Mỗi 6 con thì click lại thẻ quân 1 lần chống mất focus
                if i > 0 and i % 6 == 0:
                    self.adb.click(card_loc[0], card_loc[1])
                    time.sleep(0.2)
                    
                self.adb.click(tx, ty)
                time.sleep(random.uniform(delay_min, delay_max))

    def handle_attacking(self, screen):
        """Xử lý quá trình đánh."""
        # Gọi chiến thuật thả lính
        self.deploy_troops(screen)
        
        # Đánh xong, đợi kết thúc trận linh hoạt
        print("[ATTACKING] Đang tấn công... Chờ trận đấu kết thúc.")
        max_wait = self.config.get("battle", {}).get("max_wait_sec", 60)
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
