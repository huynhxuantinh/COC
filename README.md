# COC Auto Farm LDPlayer

Tool auto farm làng chính Clash of Clans qua LDPlayer + ADB. Dự án hiện có 2 giao diện:

- React + FastAPI: giao diện mới, nên dùng để phát triển tiếp.
- Tkinter: giao diện Python cũ, vẫn giữ lại để dự phòng.

Độ phân giải mục tiêu: `1600x900`.

## Tính năng chính

- Quét và kết nối ADB.
- Start / Tạm dừng / Tiếp tục / Stop bot.
- Tìm trận theo ngưỡng tài nguyên.
- Chọn combo, cạnh đánh, góc nhìn đánh.
- Thả quân và spell theo cấu hình.
- Theo dõi % phá hủy để đầu hàng theo điều kiện.
- Tự restart game khi OCR lỗi lâu hoặc không thấy nút Attack.
- Lưu stats theo phiên và theo device.
- Dump ảnh debug khi lỗi OCR / nhận diện.
- Tool lấy tọa độ thả quân/spell bằng ảnh mẫu hoặc ảnh chụp ADB.

## Yêu cầu cài đặt

### 1. Python

Khuyến nghị Python `3.10+`.

```powershell
python --version
```

Cài thư viện Python:

```powershell
python -m pip install -r requirements.txt
```

### 2. Node.js

Khuyến nghị Node.js `18+`.

```powershell
node -v
npm -v
```

Cài thư viện frontend:

```powershell
cd frontend
npm install
```

### 3. LDPlayer + ADB

Mở LDPlayer, bật game ở độ phân giải `1600x900`.

ADB thường nằm ở một trong các chỗ này:

- LDPlayer: `dnadb.exe`
- Android platform-tools: `adb.exe`

Nếu tool không tự tìm được ADB, điền tay trong `config.json`:

```json
"adb": {
  "path": "C:/duong/dan/toi/adb.exe",
  "device": "127.0.0.1:5555"
}
```

Kiểm tra nhanh:

```powershell
python check_env.py
```

### 4. Tesseract OCR

OCR dùng để đọc loot và % phá hủy. Nếu máy chưa có, cài Tesseract OCR rồi cấu hình:

```json
"ocr": {
  "tesseract_path": "C:/Program Files/Tesseract-OCR/tesseract.exe"
}
```

Nếu để trống, tool sẽ thử tự nhận theo đường dẫn mặc định.

## Chạy bản React + FastAPI

Mở terminal 1, chạy backend:

```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Backend chạy tại:

```text
http://127.0.0.1:8000
```

Mở terminal 2, chạy frontend:

```powershell
cd frontend
npm run dev
```

Frontend chạy tại:

```text
http://127.0.0.1:5173
```

Nếu frontend báo `Network Error`, kiểm tra:

- Backend đã chạy chưa.
- Backend đúng port `8000` chưa.
- Frontend đúng port `5173` chưa.
- Không bị firewall chặn.

## Chạy bản Tkinter cũ

Nếu muốn chạy giao diện Python cũ:

```powershell
python main.py
```

Bản Tkinter vẫn dùng chung `config.json`, logic bot và ADB.

## Luồng hoạt động bot

```text
Home
-> Attack
-> Find a Match
-> My Army Attack
-> Đọc loot
-> Next hoặc đánh
-> Zoom/kéo camera theo góc đánh
-> Thả quân/spell
-> Theo dõi trận
-> End Battle / OK nếu đủ điều kiện
-> Return Home
-> Lặp lại
```

## Các màn hình React

- Dashboard: trạng thái bot, nút Start/Pause/Stop, logs, stats.
- Farm: ngưỡng tài nguyên, combo, cạnh đánh, góc nhìn, delay.
- Đầu hàng: điều kiện dừng trận theo thời gian, % phá hủy, loot còn lại.
- Cài đặt: ADB, device, restart, OCR, runtime.
- Tọa độ: chụp ảnh ADB hoặc dùng ảnh mẫu trong `img/`, click để lưu điểm thả.

## Cấu hình quan trọng

File chính:

```text
config.json
```

Các nhóm hay chỉnh:

- `adb`: đường dẫn ADB, device.
- `farm`: combo, ngưỡng tài nguyên, cách chọn base.
- `deploy`: tọa độ, sequence thả quân, spell, delay.
- `combos`: cấu hình riêng từng combo.
- `surrender`: điều kiện đầu hàng.
- `ocr`: vùng OCR và đường dẫn Tesseract.
- `attack_timing`: delay nâng cao.

Lưu ý: combo đang chạy lấy cấu hình từ:

```json
combos["Rồng Điện"].deploy
```

Không chỉ lấy từ `deploy` gốc.

Combo hiện có:

- `Rồng Điện`
- `Valkyrie`

Khi chạy bot, nhận diện slot sẽ lọc theo combo đang chọn. Ví dụ combo `Valkyrie` chỉ quét các slot liên quan như `valkyrie`, `hero`, `rage`, `freeze`, không quét `dragon/balloon`.

## Lấy tọa độ thả quân/spell

Ảnh mẫu nằm trong:

```text
img/
```

Hiện có các góc:

- `trenbenphai.png`
- `trenbentrai.png`
- `duoibenphai.png`
- `duoibentrai.png`

Cách lấy:

1. Mở frontend.
2. Vào trang Tọa độ.
3. Chọn ảnh mẫu hoặc bấm Chụp từ ADB.
4. Click vào điểm muốn thả.
5. Chọn nhóm tọa độ.
6. Bấm Lưu điểm.
7. Test tap nếu cần.

Với vùng thả lính:

1. Vào trang `Tọa độ lính`.
2. Chọn một mục `Vùng thả ...`.
3. Click tối thiểu 3 điểm quanh khu vực muốn thả quân.
4. Bấm `Lưu điểm`.
5. Khi đánh đúng góc đó, bot sẽ random điểm bên trong vùng đã khoanh để thả quân.

Bot hiện chỉ thả lính bằng 4 vùng polygon:

- Vùng thả trên phải
- Vùng thả trên trái
- Vùng thả dưới phải
- Vùng thả dưới trái

Các kiểu thả lính theo tọa độ cố định, theo cạnh, theo hàng và bốn góc map đã bỏ khỏi luồng chạy.

Với vùng thả thuốc:

1. Vào trang `Tọa độ thuốc`.
2. Chọn nhóm thuốc kèm góc nhìn, ví dụ `Nộ 1 - trên phải`, `Băng - dưới trái`.
3. Click tối thiểu 3 điểm quanh khu vực muốn thả spell.
4. Bấm `Lưu điểm`.
5. Khi đánh ở góc nào, bot sẽ random điểm bên trong vùng spell của đúng góc đó.

Bot hiện không còn thả thuốc bằng tọa độ điểm cố định. Thuốc cũng có 4 vùng theo góc nhìn giống lính:

- Trên phải
- Trên trái
- Dưới phải
- Dưới trái

## Stats và debug

Stats:

```text
stats/
stats.json
```

Ảnh debug:

```text
debug/
```

Khi OCR fail lâu hoặc không nhận diện được màn hình, bot có thể lưu ảnh vào `debug/` để chỉnh lại vùng OCR.

## Lỗi thường gặp

### Không kết nối được backend

Chạy lại backend:

```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

### Không thấy ADB

Chạy:

```powershell
python check_env.py
```

Sau đó vào Cài đặt, bấm Quét ADB hoặc điền tay `adb.path`.

### OCR could not read loot

Thường do:

- Chưa cài Tesseract.
- Sai `ocr.tesseract_path`.
- Game chưa ở màn hình tìm trận.
- Độ phân giải không phải `1600x900`.
- Vùng OCR lệch.

### Thả quân/spell chậm

Kiểm tra cả 2 chỗ trong `config.json`:

- `deploy`
- `combos["Rồng Điện"].deploy`

Nếu combo có snapshot cũ, sửa `deploy` gốc thôi chưa đủ.

## Build kiểm tra

Kiểm tra Python:

```powershell
python -m py_compile main.py bot.py adb_client.py vision.py config_manager.py check_env.py
```

Kiểm tra frontend:

```powershell
cd frontend
npm run build
```

## Ghi chú

- Chưa cần đóng gói `.exe` ở giai đoạn hiện tại.
- Khi hoàn thiện UI và logic, có thể đóng gói bằng Electron hoặc Tauri.
- Không xóa code Tkinter cũ vì vẫn dùng làm bản dự phòng.
