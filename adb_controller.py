import subprocess
import cv2
import numpy as np
import time
import random
import os

class ADBController:
    def __init__(self, device_id="127.0.0.1:5555", adb_path=None):
        self.device_id = device_id
        if adb_path:
            self.adb_path = adb_path
        else:
            self.adb_path = r"C:\Users\ASUS\OneDrive\Documents\COC\tools\platform-tools\adb.exe"

    def run_cmd(self, cmd):
        """Chạy một lệnh ADB và trả về kết quả."""
        full_cmd = f"{self.adb_path} -s {self.device_id} {cmd}"
        try:
            result = subprocess.run(full_cmd, shell=True, capture_output=True, text=True)
            return result.stdout
        except Exception as e:
            print(f"Loi khi chay lenh ADB: {e}")
            return None

    def connect(self):
        """Ket noi toi LDPlayer qua ADB."""
        print(f"Dang ket noi toi {self.device_id}...")
        subprocess.run(f"{self.adb_path} connect {self.device_id}", shell=True, capture_output=True)
        # Kiểm tra trạng thái
        devices = subprocess.run(f"{self.adb_path} devices", shell=True, capture_output=True, text=True).stdout
        if self.device_id in devices and "offline" not in devices:
            print("Ket noi thanh cong!")
            return True
        else:
            print("Ket noi that bai. Vui long bat ADB Debugging trong LDPlayer.")
            return False

    def screencap(self):
        """Chụp màn hình giả lập và chuyển thành mảng numpy cho OpenCV."""
        # Tránh dùng exec-out trên Windows vì lỗi xuống dòng \r\n làm hỏng ảnh
        self.run_cmd("shell screencap -p /sdcard/bot_screen.png")
        self.run_cmd("pull /sdcard/bot_screen.png bot_screen.png")
        
        if not os.path.exists("bot_screen.png"):
            return None
            
        img = cv2.imread("bot_screen.png", cv2.IMREAD_COLOR)
        return img

    def click(self, x, y, randomize=True):
        """Click vào tọa độ (x, y) với độ lệch ngẫu nhiên để tránh bị phát hiện bot."""
        if randomize:
            x += random.randint(-5, 5)
            y += random.randint(-5, 5)
        
        # Đảm bảo tọa độ không bị âm
        x = max(0, x)
        y = max(0, y)
        
        self.run_cmd(f"shell input tap {x} {y}")
        # Thêm một chút delay sau khi click
        time.sleep(random.uniform(0.1, 0.3))

    def swipe(self, x1, y1, x2, y2, duration=300):
        """Vuốt màn hình (Dùng để cuộn hoặc di chuyển map)."""
        self.run_cmd(f"shell input swipe {x1} {y1} {x2} {y2} {duration}")
        time.sleep(random.uniform(0.2, 0.5))

if __name__ == "__main__":
    # Test thử kết nối
    bot = ADBController()
    bot.connect()
