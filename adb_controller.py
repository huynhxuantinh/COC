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
        """Chụp màn hình giả lập bằng pipe trực tiếp (không lưu file trung gian) và tự động reconnect nếu lỗi."""
        # Dùng shell screencap -p qua stdout pipe, thay thế CRLF thành LF để tránh lỗi corrupt trên Windows
        cmd = [self.adb_path, "-s", self.device_id, "shell", "screencap", "-p"]
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=5)
            data = result.stdout
            
            if not data:
                print(f"[!] ADB không phản hồi (có thể mất kết nối). Đang thử reconnect...")
                self.connect()
                return None
                
            # Xử lý vấn đề \r\n trên Windows
            data = data.replace(b'\r\n', b'\n')
            
            # Giải mã bằng opencv
            img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
            if img is None:
                print(f"[!] Lỗi giải mã ảnh từ ADB. Đang thử reconnect...")
                self.connect()
                
            return img
        except subprocess.TimeoutExpired:
            print(f"[!] ADB Timeout! Mất kết nối. Đang thử reconnect...")
            self.connect()
            return None
        except Exception as e:
            print(f"[!] Lỗi screencap: {e}")
            return None

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
