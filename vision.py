import cv2
import numpy as np
import pytesseract
from PIL import Image
import os

# Cấu hình đường dẫn Tesseract nếu cần thiết (trên Windows)
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

class Vision:
    def __init__(self, template_dir="templates"):
        self.template_dir = template_dir
        if not os.path.exists(self.template_dir):
            os.makedirs(self.template_dir)
            print(f"Đã tạo thư mục '{self.template_dir}'. Vui lòng thêm các ảnh mẫu vào đây.")

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

    def read_resources(self, screen_img, region):
        """
        Đọc số lượng tài nguyên từ một vùng cụ thể trên màn hình.
        region: (x, y, width, height)
        """
        x, y, w, h = region
        roi = screen_img[y:y+h, x:x+w]
        
        # Tiền xử lý ảnh để OCR đọc tốt hơn (chuyển xám, tăng độ tương phản...)
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        # Thresholding (đảo ngược hoặc nhị phân hóa tùy thuộc vào màu chữ trong game)
        # Trong COC chữ thường màu trắng có viền đen
        ret, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
        
        # Dùng pytesseract để nhận dạng số
        # Cấu hình chỉ nhận số: -c tessedit_char_whitelist=0123456789
        config = '--psm 7 -c tessedit_char_whitelist=0123456789'
        pil_img = Image.fromarray(thresh)
        text = pytesseract.image_to_string(pil_img, config=config)
        
        # Lọc kết quả và chuyển thành số nguyên
        clean_text = "".join(filter(str.isdigit, text))
        if clean_text:
            return int(clean_text)
        return 0

if __name__ == "__main__":
    v = Vision()
    # Test OCR nếu có ảnh mẫu
