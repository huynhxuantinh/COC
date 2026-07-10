import cv2
import numpy as np
import pytesseract
from PIL import Image
import os
import shutil

class Vision:
    def __init__(self, template_dir="templates", config=None):
        self.template_dir = template_dir
        self.config = config or {}
        if not os.path.exists(self.template_dir):
            os.makedirs(self.template_dir)
            print(f"Đã tạo thư mục '{self.template_dir}'. Vui lòng thêm các ảnh mẫu vào đây.")
            
        self._setup_tesseract()

    def _setup_tesseract(self):
        """Thiết lập đường dẫn tesseract hợp lệ."""
        # 1. Thử đọc từ config
        tess_path = self.config.get("system", {}).get("tesseract_path", None)
        
        # 2. Thử tìm trong hệ thống
        if not tess_path or not os.path.exists(tess_path):
            tess_path = shutil.which("tesseract")
            
        # 3. Thử fallback trên Windows
        if not tess_path:
            fallback = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
            if os.path.exists(fallback):
                tess_path = fallback
                
        if tess_path:
            pytesseract.pytesseract.tesseract_cmd = tess_path
            # print(f"[*] Sử dụng Tesseract OCR tại: {tess_path}")
        else:
            print("[!] CẢNH BÁO: Không tìm thấy Tesseract OCR. Nhận diện số có thể bị lỗi.")

    def find_template(self, screen_img, template_name, threshold=0.8):
        """
        Tìm kiếm một ảnh mẫu (template) trên màn hình.
        Trả về tọa độ (x, y) trung tâm của vùng tìm thấy, hoặc None nếu không thấy.
        """
        template_path = os.path.join(self.template_dir, template_name)
        if not os.path.exists(template_path):
            print(f"Không tìm thấy template: {template_path}")
            return None

        template = cv2.imread(template_path, cv2.IMREAD_COLOR)
        if template is None or screen_img is None:
            return None

        # Template matching
        res = cv2.matchTemplate(screen_img, template, cv2.TM_CCOEFF_NORMED)
        loc = np.where(res >= threshold)
        
        # Nếu có ít nhất 1 kết quả đạt yêu cầu
        if len(loc[0]) > 0:
            # Lấy kết quả tốt nhất
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
            # Tọa độ góc trên bên trái
            top_left = max_loc
            # Tính toán tọa độ trung tâm
            h, w = template.shape[:-1]
            center_x = top_left[0] + w // 2
            center_y = top_left[1] + h // 2
            return (center_x, center_y)
        
        return None

    def read_number_region(self, screen_img, region, scale=1.0, whitelist='0123456789'):
        """
        Đọc số từ một vùng cụ thể. Có hỗ trợ scale ảnh để OCR đọc tốt hơn các số nhỏ.
        region: (x, y, width, height)
        """
        x, y, w, h = region
        if x < 0 or y < 0 or y+h > screen_img.shape[0] or x+w > screen_img.shape[1]:
            return 0
            
        roi = screen_img[y:y+h, x:x+w]
        
        # Scale ảnh nếu cần
        if scale != 1.0:
            roi = cv2.resize(roi, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
            
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        ret, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        config_ocr = f'--psm 7 -c tessedit_char_whitelist={whitelist}'
        pil_img = Image.fromarray(thresh)
        text = pytesseract.image_to_string(pil_img, config=config_ocr)
        
        clean_text = "".join(filter(str.isdigit, text))
        if clean_text:
            return int(clean_text)
        return -1

    def read_resources(self, screen_img, region):
        """Đọc số lượng vàng/dầu (không scale để tối ưu tốc độ nếu số đủ lớn)."""
        res = self.read_number_region(screen_img, region, scale=1.0)
        return res if res != -1 else 0
        
    def read_troop_count(self, screen_img, card_center, offset):
        """
        Đọc số quân còn lại trên thẻ bài.
        offset = [x_start, y_start, x_end, y_end] (tương đối so với tâm thẻ quân)
        """
        cx, cy = card_center
        dx1, dy1, dx2, dy2 = offset
        region = (cx + dx1, cy + dy1, dx2 - dx1, dy2 - dy1)
        # Số lượng quân rất nhỏ, cần scale x2. Có chữ x đứng trước số quân (vd: x97)
        return self.read_number_region(screen_img, region, scale=2.0, whitelist='x0123456789')

if __name__ == "__main__":
    v = Vision()
    # Test OCR nếu có ảnh mẫu
