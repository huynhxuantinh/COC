# Ghi chú chuyển Tkinter sang React + FastAPI

## Mục tiêu

Tách giao diện khỏi logic Python cũ.

- Tkinter cũ vẫn giữ ở root.
- React + FastAPI là hướng phát triển chính.
- Logic đánh vẫn dùng lại `FarmBot`, `ADBClient`, `Vision`, `SlotDetector`, `config_manager`.
- Chưa đóng gói `.exe` ở giai đoạn này.

## Kiến trúc mới

```text
frontend/
  src/components/
  src/pages/
  src/services/
  src/hooks/
  src/styles/

backend/
  main.py
  routers/
  services/
  models/
```

React gọi API qua service trong `frontend/src/services/`, component không gọi bot Python trực tiếp.

## Bảng đối chiếu chức năng

| Chức năng cũ | Màn React | API/backend |
| --- | --- | --- |
| Quét ADB | Tổng quan | `POST /api/bot/scan-adb` |
| Start bot | Tổng quan | `POST /api/bot/start` |
| Pause/Resume | Tổng quan | `POST /api/bot/pause-toggle` |
| Stop bot | Tổng quan | `POST /api/bot/stop` |
| Status bot | Sidebar + Tổng quan | `GET /api/bot/status` |
| Logs realtime | Tổng quan | `GET /api/logs` |
| Xóa log | Tổng quan | `DELETE /api/logs` |
| Stats | Tổng quan | `GET /api/stats` |
| Số quân thủ công | Tổng quan | `GET/PUT /api/config` |
| Ngưỡng farm | Farm | `GET/PUT /api/config` |
| Chọn combo/góc đánh | Farm | `GET/PUT /api/config` |
| CRUD combo/lính | Combo | `GET/PUT /api/config` |
| Nhận diện slot | Nhận diện slot | API slot/template trong backend |
| Tọa độ lính | Tọa độ lính | API tọa độ trong backend |
| Tọa độ thuốc | Tọa độ thuốc | API tọa độ trong backend |
| Điều kiện đầu hàng | Đầu hàng | `GET/PUT /api/config` |
| ADB/OCR/restart | Cài đặt | `GET/PUT /api/config` |

## Các màn React hiện có

### Tổng quan

- Scan ADB.
- Start/Pause/Resume/Stop.
- Số quân thủ công.
- Stats.
- Logs.

### Farm

- Combo.
- Góc đánh.
- Ngưỡng vàng/dầu/tổng.
- Max next.
- Cơ chế tự phục hồi.

### Combo

- Tạo/sửa/copy/xóa combo.
- Thêm/sửa/xóa lính.
- Sắp xếp quân trong combo.
- Giữ tọa độ lính/thuốc ở trang riêng.

### Nhận diện slot

- Chụp ADB.
- Crop/lưu template icon.
- Test nhận diện.

### Tọa độ lính

- Lưu vùng polygon thả lính theo combo và 4 góc nhìn.

### Tọa độ thuốc

- Lưu vùng polygon thả thuốc theo combo và 4 góc nhìn.

### Đầu hàng

- Điều kiện dừng trận.
- Damage stall.
- Damage unknown restart.

### Cài đặt

- ADB.
- Device.
- OCR/Tesseract.
- Restart.
- Zoom home.
- LDPlayer index.
- Timing.

## Dữ liệu

Không dùng SQL/PostgreSQL.

```text
config.json
stats/
debug/
img/
img/slots/
```

## Chạy local

Backend:

```powershell
python -m pip install -r requirements.txt
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

Frontend mặc định gọi:

```text
http://127.0.0.1:8000
```

Nếu cần đổi API:

```powershell
$env:VITE_API_BASE_URL="http://127.0.0.1:8000"
npm run dev
```

Nếu frontend chạy port khác, cấu hình CORS:

```powershell
$env:COC_CORS_ORIGINS="http://127.0.0.1:5173,http://localhost:5173"
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

## Ghi chú

- Không xóa code Tkinter cũ.
- Không rewrite thuật toán đánh trong giai đoạn chuyển UI.
- Các tính năng mới nên ưu tiên đi qua FastAPI + React.
- Khi ổn định mới tính Electron/Tauri để đóng gói `.exe`.
