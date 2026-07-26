# Mô tả chi tiết COC Auto Farm Tool

## 1. Mục tiêu của tool

COC Auto Farm Tool là tool chạy local để tự động farm tài nguyên ở làng chính Clash of Clans qua LDPlayer. Tool điều khiển giả lập bằng ADB, đọc màn hình bằng OCR/vision, sau đó tự thao tác theo kịch bản đã cấu hình.

Mục tiêu chính hiện tại:

- Farm vàng và dầu ở làng chính.
- Tìm base theo ngưỡng tài nguyên người dùng đặt.
- Tự Next nếu base không đạt.
- Tự chọn góc đánh, zoom/kéo camera, thả quân và thuốc.
- Theo dõi trận, đầu hàng/về làng theo điều kiện cấu hình.
- Có giao diện React để cấu hình, xem log, xem stats và lấy tọa độ.

Độ phân giải mục tiêu:

```text
LDPlayer: 1600x900
```

## 2. Kiến trúc tổng quan

Tool hiện có 3 phần chính:

```text
React UI
  -> gọi API
FastAPI backend
  -> bọc logic Python
Bot core Python
  -> ADB, OCR, vision, deploy, monitor battle
```

### Frontend

Thư mục:

```text
frontend/
```

Công nghệ:

- React
- Vite
- Tailwind CSS
- Axios/fetch qua service riêng

Frontend chỉ làm giao diện và gọi API. Component không gọi trực tiếp logic bot.

### Backend

Thư mục:

```text
backend/
```

Công nghệ:

- Python FastAPI
- Uvicorn

Backend nhận lệnh từ React rồi gọi lại logic Python có sẵn.

### Bot core

Các file chính:

```text
bot.py
adb_client.py
vision.py
slot_detector.py
config_manager.py
bot_runtime.py
```

Nhiệm vụ:

- Kết nối ADB.
- Chụp màn hình LDPlayer.
- OCR vàng/dầu, % phá hủy, màn hình kết quả.
- Detect slot quân/thuốc bằng template matching.
- Thả quân trong vùng polygon.
- Thả thuốc theo vùng polygon riêng.
- Theo dõi trận và xử lý đầu hàng/về làng.

## 3. Dữ liệu lưu ở đâu

Tool chưa dùng SQL, PostgreSQL hay database server.

Hiện tại dữ liệu lưu bằng file JSON và ảnh local:

```text
config.json          Cấu hình chính
stats/               Stats theo device/phiên
debug/               Ảnh debug khi OCR/vision lỗi
img/                 Ảnh mẫu 4 góc
img/slots/           Mẫu icon quân/thuốc để nhận diện slot
```

File quan trọng nhất là:

```text
config.json
```

File này chứa:

- ADB path/device.
- Ngưỡng farm.
- Combo đang dùng.
- Vùng thả quân.
- Vùng thả thuốc.
- Điều kiện đầu hàng.
- Vùng OCR.
- Delay/timing.
- Cấu hình detect slot.

## 4. Luồng chạy bot

Luồng chính:

```text
Home
-> Attack
-> Find a Match
-> đọc loot vàng/dầu
-> nếu không đạt thì Next
-> nếu đạt thì đánh
-> random hoặc chọn góc đánh
-> zoom nhỏ
-> kéo camera theo góc
-> nhận diện slot quân/thuốc
-> thả quân trong vùng polygon
-> thả thuốc trong vùng polygon riêng
-> theo dõi % phá hủy
-> đầu hàng hoặc chờ kết quả
-> đọc tài nguyên thực nhận ở Victory screen
-> Return Home
-> lặp lại
```

Bot hiện chỉ quan tâm farm:

- Vàng
- Dầu

Dầu đen đã bỏ khỏi luồng đọc/tính ngưỡng chính.

## 5. Các trang giao diện React

### 5.1. Tổng quan

Chức năng:

- Quét ADB.
- Bắt đầu bot.
- Tạm dừng/tiếp tục.
- Dừng bot.
- Xem trạng thái ADB/bot.
- Nhập số quân thủ công nếu không muốn OCR số lượng.
- Xem stats phiên.
- Xem log realtime.
- Xóa log.

Lưu ý:

- Nếu bật số quân thủ công, bot dùng số lượng người dùng nhập.
- Bot vẫn cần nhận diện vị trí slot trên thanh quân để biết tap vào đâu.

### 5.2. Farm

Chức năng:

- Chọn combo.
- Chọn góc đánh hoặc random góc.
- Chọn kiểu xét ngưỡng: `any`, `all`, `total`.
- Nhập ngưỡng vàng tối thiểu.
- Nhập ngưỡng dầu tối thiểu.
- Nhập tổng vàng + dầu tối thiểu.
- Nhập số lần Next tối đa.
- Bật/tắt các cơ chế tự phục hồi.

Các cơ chế tự phục hồi:

- Restart game nếu không thấy nút Attack.
- Restart khi OCR loot fail quá lâu.
- Dừng bot sau số lỗi cycle liên tiếp.
- Auto-stop nếu bật.

### 5.3. Tọa độ lính

Chức năng:

- Dùng ảnh mẫu trong `img/`.
- Hoặc chụp trực tiếp từ ADB.
- Click nhiều điểm để tạo vùng polygon.
- Lưu vùng thả quân theo combo.
- Test tap một điểm.

Hiện chỉ dùng 4 vùng thả quân:

```text
Vùng thả trên phải
Vùng thả trên trái
Vùng thả dưới phải
Vùng thả dưới trái
```

Bot không còn phụ thuộc vào kiểu thả lính theo tọa độ cố định/cạnh/hàng cũ.

### 5.4. Tọa độ thuốc

Chức năng:

- Tách riêng khỏi trang tọa độ lính.
- Cấu hình vùng thả thuốc theo 4 góc giống lính.
- Dùng cho nhóm Nộ/Băng linh hoạt.

Hiện thuốc cũng dùng vùng polygon:

```text
Nhóm Nộ/Băng - trên phải
Nhóm Nộ/Băng - trên trái
Nhóm Nộ/Băng - dưới phải
Nhóm Nộ/Băng - dưới trái
```

Khi đánh ở góc nào, bot lấy vùng thuốc tương ứng góc đó để random điểm cast.

### 5.5. Nhận diện slot

Chức năng:

- Chụp màn hình từ ADB.
- Khoanh/crop icon quân hoặc thuốc trên thanh quân.
- Lưu mẫu icon vào `img/slots/`.
- Test nhận diện slot.
- Hiển thị kết quả nhận diện: loại slot, số lượng, tọa độ, score.

Các loại đang hỗ trợ:

```text
dragon
balloon
valkyrie
hero
rage
freeze
```

Tên hiển thị:

```text
Rồng điện
Bóng
Valkyrie
Tướng
Nộ
Băng
```

### 5.6. Đầu hàng

Chức năng:

- Đầu hàng theo thời gian.
- Đầu hàng theo % phá hủy.
- Đầu hàng khi tài nguyên còn lại thấp.
- Không đầu hàng, đánh hết.
- Giới hạn thời lượng trận.
- Dừng trận nếu damage đứng yên quá lâu.
- Lọc OCR damage nhảy bất thường.

### 5.7. Cài đặt

Chức năng:

- ADB path.
- Device.
- Package game.
- Kết nối ADB khi bắt đầu.
- Quét sâu tìm ADB.
- Bật/tắt OCR.
- Tesseract path.
- Restart game định kỳ.
- Delay nâng cao.
- Mở nhanh trang tọa độ thuốc.

## 6. Combo hiện có

### Rồng Điện

Sequence hiện tại:

```text
dragon
balloon
hero
```

Spell group:

```text
rage
freeze
```

Bot chỉ nhận diện các slot liên quan combo đang chạy, không quét toàn bộ mọi loại nếu combo không cần.

### Valkyrie

Sequence hiện tại:

```text
valkyrie
hero
```

Spell group:

```text
rage
freeze
```

## 7. Nhận diện quân/thuốc

Bot có 2 cách lấy số lượng:

### Cách 1: Tự detect slot

Bot chụp màn hình, dùng template matching để tìm icon slot trên thanh quân.

Kết quả gồm:

- Loại slot.
- Tọa độ slot.
- Số lượng đọc được.
- Score nhận diện.

Slot nào không có thì skip.

### Cách 2: Nhập số lượng thủ công

Trong trang Tổng quan có mục `Số quân thủ công`.

Nếu bật:

- Người dùng nhập số quân/thuốc theo combo.
- Bot dùng số đó để quyết định thả bao nhiêu.
- Bot vẫn detect vị trí slot để tap đúng icon.

Cách này dùng khi OCR số lượng chưa ổn hoặc muốn test nhanh.

## 8. Nguyên tắc thả quân

Bot không thả quân theo một list tọa độ cố định nữa.

Hiện tại:

```text
Chọn góc đánh
-> zoom/kéo camera theo góc
-> lấy vùng polygon tương ứng góc
-> random điểm bên trong vùng
-> thả quân vào các điểm random đó
```

Ưu điểm:

- Dễ chỉnh hơn khi base lệch.
- Ít phụ thuộc từng điểm cố định.
- Có thể thay đổi vùng cho từng góc.

## 9. Nguyên tắc thả thuốc

Thuốc đã được tách riêng khỏi tọa độ lính.

Hiện tại:

```text
Chọn góc đánh
-> lấy vùng spell của góc đó
-> chọn slot Nộ/Băng còn phép
-> cast vào điểm random trong vùng
```

Tool hiện dùng `spell_groups`, không dùng cấu hình spell riêng kiểu No1/Băng/No2 nữa.

## 10. OCR và vùng đọc

OCR dùng để đọc:

- Vàng/dầu khi đang tìm trận.
- % phá hủy trong trận.
- Vàng/dầu thực nhận ở màn hình Victory.

Các vùng OCR nằm trong:

```json
ocr.regions
```

Một số vùng quan trọng:

```text
loot_panel
loot_gold
loot_elixir
damage_percent
result_loot_panel
result_gold
result_elixir
home_attack_button
```

Nếu OCR sai, cần kiểm tra:

- Game đúng 1600x900 chưa.
- Camera/màn hình có đúng trạng thái không.
- Vùng OCR có lệch không.
- Tesseract path đúng chưa.
- Ảnh debug trong `debug/`.

## 11. Stats

Stats được ghi ra file trong:

```text
stats/
```

Các chỉ số chính:

```text
attacks
next
gold_seen
elixir_seen
```

Vàng/dầu thực nhận được đọc ở màn hình Victory, không lấy từ màn hình tìm trận.

## 12. Debug

Khi lỗi OCR hoặc màn hình không đúng trạng thái, bot có thể dump ảnh vào:

```text
debug/
```

Ảnh debug dùng để:

- Kiểm tra bot đang thấy màn hình gì.
- Chỉnh lại vùng OCR.
- Chỉnh lại nhận diện nút Attack.
- Chỉnh template slot quân/thuốc.

## 13. Các cơ chế bảo vệ

Bot có các cơ chế tránh treo vô hạn:

- Screencap ADB có retry.
- Validate PNG trước khi mở ảnh.
- Một lỗi cycle không làm chết cả bot ngay.
- Circuit breaker nếu lỗi liên tiếp quá ngưỡng.
- Restart nếu không thấy nút Attack nhiều lần.
- Restart nếu OCR loot fail quá lâu.
- Auto-stop chỉ xử lý ở ranh giới an toàn giữa các trận.
- Dump debug khi lỗi kéo dài.

## 14. Cách chạy local

### Backend

```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Backend:

```text
http://127.0.0.1:8000
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Frontend:

```text
http://127.0.0.1:5173
```

Nếu frontend báo `Network Error`, kiểm tra backend đã chạy ở port `8000` chưa.

## 15. Cách test cơ bản

1. Mở LDPlayer 1600x900.
2. Mở Clash of Clans ở làng chính.
3. Chạy backend.
4. Chạy frontend.
5. Vào Tổng quan.
6. Bấm `Quét ADB`.
7. Kiểm tra log thấy ADB connected.
8. Chọn combo ở Farm.
9. Kiểm tra tọa độ lính/thuốc đã có đủ 4 góc.
10. Nếu chưa tin OCR số lượng, bật `Số quân thủ công`.
11. Bấm `Bắt đầu`.
12. Theo dõi log.

## 16. Lưu ý khi phát triển tiếp

Các hướng nâng cấp hợp lý:

- Cải thiện OCR damage vì hiện vẫn là vùng dễ lệch.
- Hoàn thiện template slot cho từng combo.
- Thêm combo mới theo cấu trúc riêng.
- Tự chọn góc đánh theo vị trí kho tài nguyên bằng vision.
- Tách config theo profile/account.
- Đóng gói thành app Windows bằng Electron hoặc Tauri sau khi UI ổn định.

Khi thêm combo mới, cần có:

- Sequence quân.
- Spell group.
- Template icon slot cần nhận diện.
- Vùng thả quân 4 góc.
- Vùng thả thuốc 4 góc.
- Ngưỡng/timing phù hợp.

## 17. Tóm tắt ngắn

Tool này là một hệ thống auto farm local:

```text
React UI cấu hình
-> FastAPI nhận lệnh
-> Python bot điều khiển LDPlayer qua ADB
-> OCR/vision đọc màn hình
-> detect slot quân/thuốc
-> thả quân/thuốc theo vùng
-> theo dõi trận
-> lưu stats/debug
```

Hiện tại hướng chính là farm vàng + dầu, dùng vùng polygon cho cả lính và thuốc, nhận diện slot theo combo, có tùy chọn nhập số quân thủ công để giảm phụ thuộc OCR số lượng.
