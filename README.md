# COC Auto Farm LDPlayer

Tool auto farm làng chính Clash of Clans qua LDPlayer + ADB.

Kiến trúc hiện tại:

- Frontend: React + Vite + Tailwind CSS
- Backend: Python FastAPI
- Bot core: Python, ADB, OCR, OpenCV/template matching
- UI cũ Tkinter vẫn giữ lại để dự phòng

Độ phân giải mục tiêu: `1600x900`.

## Chức năng chính

- Quét và kết nối ADB.
- Start / Pause / Resume / Stop bot.
- Tìm trận theo ngưỡng vàng và dầu.
- Next nếu base không đạt.
- Chọn combo farm.
- CRUD combo và loại lính trên UI.
- Nhận diện slot quân/thuốc bằng template trong `img/slots/`.
- Hỗ trợ nhập số quân thủ công nếu không muốn đọc số lượng bằng OCR.
- Thả lính theo vùng polygon 4 góc nhìn.
- Thả thuốc theo vùng polygon riêng 4 góc nhìn.
- Theo dõi % phá hủy để đầu hàng hoặc chờ kết quả.
- Đọc vàng/dầu nhận được ở màn Victory.
- Lưu stats theo device.
- Dump ảnh debug khi OCR/vision lỗi.

## Cài đặt

### Python

Khuyến nghị Python `3.10+`.

```powershell
python --version
python -m pip install -r requirements.txt
```

### Node.js

Khuyến nghị Node.js `18+`.

```powershell
node -v
npm -v
cd frontend
npm install
```

### LDPlayer + ADB

Mở LDPlayer ở độ phân giải `1600x900`.

ADB thường nằm ở:

- `D:\LDPlayer\LDPlayer9\adb.exe`
- `D:\LDPlayer\LDPlayer9\dnadb.exe`
- Android platform-tools `adb.exe`

Nếu tool không tự tìm được ADB, cấu hình tay trong `config.json`:

```json
"adb": {
  "path": "D:/LDPlayer/LDPlayer9/adb.exe",
  "device": "127.0.0.1:5555"
}
```

Kiểm tra môi trường:

```powershell
python check_env.py
```

### Tesseract OCR

OCR dùng để đọc loot và damage.

Nếu máy chưa có Tesseract, cài rồi cấu hình:

```json
"ocr": {
  "tesseract_path": "C:/Program Files/Tesseract-OCR/tesseract.exe"
}
```

## Chạy local

Terminal 1, chạy backend:

```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Backend:

```text
http://127.0.0.1:8000
```

Terminal 2, chạy frontend:

```powershell
cd frontend
npm run dev
```

Frontend:

```text
http://127.0.0.1:5173
```

Nếu frontend báo `Network Error`, kiểm tra backend đã chạy đúng port `8000` chưa.

## Chạy UI Tkinter cũ

```powershell
python main.py
```

UI Tkinter dùng chung `config.json` và logic bot, nhưng hướng phát triển chính là React + FastAPI.

## Luồng bot

```text
Home
-> zoom nhỏ ở làng chính
-> Attack
-> Find a Match
-> đọc vàng/dầu
-> Next hoặc đánh
-> chọn/random góc nhìn
-> zoom/kéo camera theo góc
-> nhận diện slot quân/thuốc
-> thả lính trong vùng polygon
-> thả thuốc trong vùng polygon
-> theo dõi damage
-> End Battle hoặc chờ result
-> đọc vàng/dầu nhận được ở Victory
-> Return Home
-> lặp lại
```

## Các trang React

### Tổng quan

- Quét ADB.
- Start / Pause / Resume / Stop.
- Nhập số quân thủ công.
- Xem stats.
- Xem log realtime.
- Log có chế độ gọn/chi tiết.

### Farm

- Chọn combo.
- Chọn góc đánh hoặc random.
- Đặt ngưỡng vàng/dầu/tổng.
- Đặt số lần Next tối đa.
- Bật/tắt cơ chế tự phục hồi.

### Combo

Quản lý combo và lính.

Combo:

- Tạo combo.
- Đổi tên combo.
- Copy combo.
- Xóa combo.
- Chọn combo đang chạy.

Lính:

- Thêm loại lính.
- Đổi tên lính.
- Xóa lính.
- Khi đổi tên lính, config tự đổi theo trong combo, số quân thủ công và tọa độ slot nếu có.
- Nếu lính đang được dùng trong combo, UI chặn xóa để tránh hỏng config.

Quân trong combo:

- `Loại`: loại quân sẽ thả.
- `Số lượng`: `all` là thả hết, hoặc nhập số cụ thể.
- `Tối đa`: giới hạn số tap.
- `Delay`: thời gian giữa mỗi tap.

### Nhận diện slot

- Chụp ảnh từ ADB.
- Crop icon quân/thuốc.
- Lưu mẫu vào `img/slots/`.
- Test nhận diện slot.
- Bot chỉ quét các loại slot liên quan combo đang chạy.

### Tọa độ lính

- Set vùng thả lính theo combo.
- Mỗi combo có 4 vùng:
  - Trên phải
  - Trên trái
  - Dưới phải
  - Dưới trái
- Mỗi vùng cần ít nhất 3 điểm polygon.

### Tọa độ thuốc

- Set vùng thả thuốc riêng theo combo.
- Thuốc cũng có 4 vùng theo góc nhìn giống lính.
- Bot random điểm trong vùng và có giới hạn khoảng cách để giảm trùng điểm cast.

### Đầu hàng

- Đầu hàng theo thời gian.
- Đầu hàng theo % phá hủy.
- Đầu hàng khi tài nguyên còn lại thấp.
- Dừng trận nếu damage đứng yên quá lâu.
- Restart game nếu damage OCR toàn `?` quá ngưỡng.

### Cài đặt

- ADB path.
- Device.
- Package game.
- Tesseract path.
- OCR.
- Restart game.
- Zoom camera ở home.
- LDPlayer index.
- Delay nâng cao.

## Dữ liệu lưu ở đâu

Tool không dùng SQL/PostgreSQL.

Dữ liệu lưu bằng file local:

```text
config.json        Cấu hình chính
stats/             Stats theo device
debug/             Ảnh debug OCR/vision
img/               Ảnh mẫu 4 góc
img/slots/         Template icon quân/thuốc
```

## Config quan trọng

Các nhóm chính trong `config.json`:

- `adb`: ADB path/device.
- `game`: package, resolution, restart, zoom.
- `farm`: combo, ngưỡng tài nguyên, góc đánh.
- `combos`: cấu hình deploy riêng từng combo.
- `deploy`: deploy mặc định.
- `slot_detection`: danh sách loại slot và template matching.
- `manual_army`: số quân thủ công.
- `surrender`: điều kiện dừng trận.
- `ocr`: vùng OCR và Tesseract.
- `attack_timing`: delay nâng cao.

Combo đang chạy ưu tiên lấy từ:

```text
combos[config.farm.combo].deploy
```

Không chỉ lấy từ `deploy` gốc.

## Cách thêm combo mới

1. Vào trang Combo.
2. Tạo combo mới.
3. Thêm hoặc chọn loại lính cần dùng.
4. Thêm quân vào `Quân trong combo`.
5. Lưu cấu hình.
6. Vào Nhận diện slot, lưu template icon cho các loại lính/thuốc cần detect.
7. Vào Tọa độ lính, set 4 vùng thả cho combo đó.
8. Vào Tọa độ thuốc, set 4 vùng spell cho combo đó.
9. Test nhận diện slot.
10. Chạy bot.

## Cách thêm lính mới

1. Vào trang Combo.
2. Nhập tên lính mới, ví dụ `witch`, `baby dragon`, `rồng`.
3. Tool tự chuẩn hóa tên thành mã không dấu, ví dụ `rồng` -> `rong`.
4. Lưu cấu hình.
5. Vào Nhận diện slot để lưu mẫu icon cho lính đó.
6. Thêm lính đó vào combo cần dùng.

## Stats và debug

Stats nằm trong:

```text
stats/
```

Ảnh debug nằm trong:

```text
debug/
```

Khi OCR fail lâu hoặc màn hình sai trạng thái, bot có thể lưu ảnh debug để chỉnh lại vùng OCR/template.

## Lỗi thường gặp

### Network Error

Backend chưa chạy hoặc sai port.

```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

### Không thấy ADB

```powershell
python check_env.py
```

Hoặc vào Cài đặt, bấm Quét ADB.

### OCR không đọc được loot

Kiểm tra:

- Tesseract path.
- Game đang ở màn tìm trận.
- Resolution `1600x900`.
- Vùng OCR `ocr.regions`.
- Ảnh debug trong `debug/`.

### Nhận diện sai số quân

Cách xử lý nhanh:

- Bật số quân thủ công ở Tổng quan.
- Hoặc lưu lại template slot rõ hơn trong Nhận diện slot.

## Kiểm tra build

Python:

```powershell
python -m py_compile main.py bot.py adb_client.py vision.py config_manager.py check_env.py
```

Frontend:

```powershell
cd frontend
npm run build
```

## Ghi chú

- Chưa đóng gói `.exe` ở giai đoạn này.
- Khi UI và logic ổn định, có thể đóng gói bằng Electron hoặc Tauri.
- Không xóa code Tkinter cũ.
