# Tách Tkinter sang React + FastAPI

## Chức năng đọc từ Tkinter hiện tại

| Nhóm chức năng | Chức năng hiện có | Hàm Tkinter/Python đang gọi |
| --- | --- | --- |
| Điều khiển bot | Quét ADB, tìm `adb.exe`, thử kết nối LDPlayer, chụp màn hình kiểm tra | `scan_adb`, `_scan_adb_worker`, `ADBClient.connect`, `screencap_png` |
| Điều khiển bot | Bắt đầu bot sau khi đã quét ADB | `start_bot`, `FarmBot.run` |
| Điều khiển bot | Tạm dừng / tiếp tục bot | `toggle_pause`, `pause_event` |
| Điều khiển bot | Dừng bot | `stop_bot`, `stop_event` |
| Thống kê | Hiển thị trận, next, vàng, dầu, dầu đen từ RAM/file | `_load_saved_stats`, `_load_multi_device_stats`, `_drain_stats` |
| Logs | Hiển thị log realtime và xóa log | `_drain_logs`, `_log`, `clear_logs` |
| Farm | Combo, cạnh đánh, chế độ thả, ngưỡng vàng/dầu/dầu đen/tổng, max next, OCR fail timeout | `_build_farm_tab`, `_sync_config_from_ui` |
| Vận hành | Bỏ qua restart game, auto-stop, chờ lính, đổi combo, thống kê tài nguyên, restart nếu mất nút Attack | `_build_farm_tab`, `_sync_config_from_ui` |
| Đầu hàng | Theo thời gian, % phá hủy, ít tài nguyên, không đầu hàng, ngưỡng còn lại | `_build_surrender_tab`, `_sync_config_from_ui` |
| Cài đặt | ADB path, device, Tesseract path, Max Next | `open_settings_hint`, `_settings_row`, `_pick_file` |

## Bảng đối chiếu chức năng

| Chức năng Tkinter cũ | Màn React mới | API Python tương ứng |
| --- | --- | --- |
| Quét ADB | Tổng quan | `POST /api/bot/scan-adb` |
| Bắt đầu bot | Tổng quan | `POST /api/bot/start` |
| Tạm dừng / tiếp tục | Tổng quan | `POST /api/bot/pause-toggle` |
| Dừng bot | Tổng quan | `POST /api/bot/stop` |
| Hiển thị trạng thái bot | Sidebar + Tổng quan | `GET /api/bot/status` |
| Hiển thị thống kê phiên | Tổng quan | `GET /api/stats` |
| Hiển thị logs realtime | Tổng quan | `GET /api/logs?after=<id>` |
| Xóa logs | Tổng quan | `DELETE /api/logs` |
| Combo/cạnh đánh/chế độ thả/ngưỡng farm | Farm | `GET /api/config`, `PUT /api/config`, `GET /api/config/options` |
| Cài đặt vận hành bot | Farm | `GET /api/config`, `PUT /api/config` |
| Điều kiện đầu hàng | Đầu hàng | `GET /api/config`, `PUT /api/config` |
| ADB/device/Tesseract/OCR/restart định kỳ | Cài đặt | `GET /api/config`, `PUT /api/config` |

## Kiểm tra sau từng màn

| Màn | Giao diện | Sự kiện | Dữ liệu vào/ra | Lỗi | API thật |
| --- | --- | --- | --- | --- | --- |
| Tổng quan | Card điều khiển, stats, logs responsive | Scan/Start/Pause/Stop/Clear | Status, stats, logs | Hiển thị lỗi backend/ADB | Có |
| Farm | Form combo, cạnh đánh, ngưỡng, công tắc vận hành | Lưu cấu hình | `game`, `farm` trong config | Validate từ backend | Có |
| Đầu hàng | Form luật kết thúc trận | Lưu cấu hình | `surrender` trong config | Validate từ backend | Có |
| Cài đặt | Form ADB/OCR/restart | Lưu cấu hình | `adb`, `ocr`, `game` | Validate từ backend | Có |

## Chạy local

Backend:

```powershell
python -m pip install -r requirements.txt
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

Frontend mặc định gọi `http://127.0.0.1:8000`. Nếu cần đổi API:

```powershell
$env:VITE_API_BASE_URL="http://127.0.0.1:8000"
npm run dev
```

## Ghi chú

- Code Tkinter cũ ở gốc vẫn giữ nguyên.
- Logic đánh vẫn dùng `FarmBot`, `ADBClient`, `Vision`, `config_manager`; FastAPI chỉ bọc thành API.
- Trình duyệt không thể mở native file picker để lấy đường dẫn `.exe` giống Tkinter một cách đáng tin cậy, nên màn Cài đặt dùng ô nhập/paste path. Khi đóng gói Electron/Tauri có thể thêm file picker native.
