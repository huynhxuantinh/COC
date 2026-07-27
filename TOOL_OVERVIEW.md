# Mô tả chi tiết COC Auto Farm Tool

## Mục tiêu

COC Auto Farm Tool là tool chạy local để farm vàng và dầu ở làng chính Clash of Clans qua LDPlayer. Tool dùng ADB để thao tác giả lập, OCR/vision để đọc màn hình, sau đó tự chạy theo cấu hình người dùng đặt trong UI.

Độ phân giải mục tiêu:

```text
1600x900
```

## Kiến trúc

```text
React UI
-> FastAPI backend
-> Python bot core
-> ADB / OCR / OpenCV
-> LDPlayer
```

Các file core:

```text
bot.py
adb_client.py
vision.py
slot_detector.py
config_manager.py
bot_runtime.py
backend/services/bot_service.py
```

## Dữ liệu

Tool không dùng database server.

```text
config.json        Cấu hình chính
stats/             Thống kê theo device
debug/             Ảnh debug khi lỗi
img/               Ảnh mẫu góc nhìn
img/slots/         Template icon slot
```

## Luồng chạy

```text
Home
-> zoom nhỏ home
-> Attack
-> Find a Match
-> đọc vàng/dầu
-> Next nếu base thấp
-> đánh nếu base đạt
-> chọn/random góc nhìn
-> zoom/kéo camera theo góc
-> nhận diện slot quân/thuốc
-> thả lính theo vùng polygon
-> thả thuốc theo vùng polygon
-> theo dõi damage
-> đầu hàng hoặc chờ kết quả
-> đọc vàng/dầu nhận được ở Victory
-> Return Home
```

## Frontend

Frontend nằm trong:

```text
frontend/
```

Công nghệ:

- React
- Vite
- Tailwind CSS
- Axios/service API riêng

Các trang chính:

- Tổng quan
- Farm
- Combo
- Nhận diện slot
- Tọa độ lính
- Tọa độ thuốc
- Đầu hàng
- Cài đặt

## Backend

Backend nằm trong:

```text
backend/
```

Backend FastAPI bọc logic Python thành API để React gọi.

Chạy backend:

```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

## Trang Tổng quan

Chức năng:

- Quét ADB.
- Start/Pause/Resume/Stop bot.
- Nhập số quân thủ công.
- Xem stats.
- Xem log realtime.
- Xóa log.

Số quân thủ công dùng khi không muốn phụ thuộc OCR số lượng. Bot vẫn cần nhận diện vị trí slot để biết tap vào đâu.

## Trang Farm

Chức năng:

- Chọn combo.
- Chọn/random góc đánh.
- Cấu hình ngưỡng vàng/dầu/tổng.
- Cấu hình số lần Next tối đa.
- Bật/tắt cơ chế tự phục hồi.

Dark elixir không còn là tài nguyên chính để xét ngưỡng farm.

## Trang Combo

Trang này quản lý combo và loại lính.

CRUD combo:

- Tạo combo.
- Đổi tên combo.
- Copy combo.
- Xóa combo.
- Chọn combo đang chạy.

CRUD lính:

- Thêm lính.
- Đổi tên lính.
- Xóa lính.

Khi đổi tên lính, tool cập nhật theo trong:

- `slot_detection.kinds`
- `slot_detection.count_max_by_kind`
- `manual_army.counts`
- `coords.slots`
- `deploy.sequence`
- `combos[*].deploy.sequence`

Khi xóa lính, tool sẽ chặn nếu lính đó đang được dùng trong combo hoặc deploy mặc định.

## Quân trong combo

Mỗi dòng quân gồm:

- `Loại`: loại quân sẽ thả.
- `Số lượng`: `all` hoặc số cụ thể.
- `Tối đa`: giới hạn số tap.
- `Delay`: thời gian nghỉ giữa các tap.

Ví dụ:

```text
rong | all | 20 | 0.08
```

Nghĩa là chọn slot `rong`, thả hết, tối đa 20 tap, mỗi tap cách nhau 0.08 giây.

## Trang Nhận diện slot

Chức năng:

- Chụp màn hình từ ADB.
- Crop icon slot.
- Lưu template vào `img/slots/`.
- Test nhận diện.

Bot chỉ detect các loại slot liên quan combo đang chạy để giảm thời gian quét.

Các slot thường dùng:

```text
dragon
balloon
valkyrie
hero
rage
freeze
```

Có thể thêm loại mới từ trang Combo, sau đó qua Nhận diện slot để lưu mẫu icon.

## Trang Tọa độ lính

Lính thả theo vùng polygon, không còn phụ thuộc tọa độ điểm cố định.

Mỗi combo có 4 vùng:

```text
Trên phải
Trên trái
Dưới phải
Dưới trái
```

Mỗi vùng cần tối thiểu 3 điểm.

## Trang Tọa độ thuốc

Thuốc cũng thả theo vùng polygon riêng.

Mỗi combo có 4 vùng spell:

```text
Trên phải
Trên trái
Dưới phải
Dưới trái
```

Bot random điểm trong vùng spell và có cấu hình khoảng cách tối thiểu giữa 2 điểm cast để giảm trùng vị trí.

Tool dùng `spell_groups`, không còn dùng kiểu spell riêng lẻ `No1/Băng/No2`.

## Trang Đầu hàng

Chức năng:

- Dừng theo thời gian.
- Dừng theo % phá hủy.
- Dừng khi tài nguyên còn lại thấp.
- Đánh hết nếu chọn không đầu hàng.
- Dừng nếu damage đứng yên quá lâu.
- Restart nếu damage OCR liên tục là `?` quá ngưỡng.

Damage OCR là phần dễ lệch nhất, nên đã có lọc outlier và cơ chế restart khi không đọc được quá lâu.

## Trang Cài đặt

Chức năng:

- ADB path.
- Device.
- Package game.
- Tesseract path.
- OCR on/off.
- Restart game.
- Zoom camera home.
- LDPlayer index.
- Delay nâng cao.

## Cơ chế nhận diện slot

Slot detector dùng template matching OpenCV.

Nguồn template:

```text
img/slots/
```

Kết quả detect gồm:

- loại slot
- tọa độ slot
- số lượng đọc được
- score

Nếu bật số quân thủ công, bot dùng số người dùng nhập để quyết định thả bao nhiêu, nhưng vẫn detect slot để biết vị trí tap.

## Cơ chế thả lính

```text
Chọn slot quân
-> lấy vùng polygon theo góc đang đánh
-> random điểm trong vùng
-> tap thả quân
-> lặp theo số lượng/tối đa/delay
```

Không dùng các mode cũ như thả theo cạnh, thả theo hàng, 4 góc map.

## Cơ chế thả thuốc

```text
Chọn slot spell còn phép
-> lấy vùng spell theo góc đang đánh
-> random điểm trong vùng
-> tránh điểm quá gần điểm vừa cast
-> cast spell
```

Spell hiện đi theo nhóm Nộ/Băng linh hoạt.

## OCR

OCR dùng để đọc:

- vàng/dầu khi tìm trận
- damage trong trận
- vàng/dầu nhận được ở màn Victory

Các vùng OCR nằm trong:

```text
ocr.regions
```

Vùng quan trọng:

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

## Stats

Stats nằm trong:

```text
stats/
```

Chỉ số chính:

```text
attacks
next
gold_seen
elixir_seen
```

Vàng/dầu nhận thực tế được đọc ở màn Victory.

## Debug

Ảnh debug nằm trong:

```text
debug/
```

Dùng để kiểm tra:

- OCR loot
- OCR damage
- nút Attack
- màn hình result
- template slot

## Cơ chế bảo vệ

Bot có các lớp bảo vệ:

- ADB screencap retry.
- Validate PNG.
- Lỗi 1 cycle không làm chết bot ngay.
- Circuit breaker khi lỗi liên tiếp.
- Restart nếu không thấy Attack.
- Restart nếu OCR loot fail quá lâu.
- Restart nếu damage OCR `?` quá lâu.
- Auto-stop ở ranh giới an toàn.
- Dump debug khi lỗi kéo dài.

## Chạy local

Backend:

```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

## Test cơ bản

1. Mở LDPlayer `1600x900`.
2. Mở Clash of Clans ở làng chính.
3. Chạy backend.
4. Chạy frontend.
5. Vào Tổng quan, bấm Quét ADB.
6. Chọn combo ở Farm.
7. Kiểm tra template slot.
8. Kiểm tra 4 vùng tọa độ lính.
9. Kiểm tra 4 vùng tọa độ thuốc.
10. Bật số quân thủ công nếu cần.
11. Start bot.

## Hướng phát triển tiếp

- Cải thiện OCR damage.
- Tối ưu template slot theo nhiều army.
- Thêm combo bằng UI thay vì sửa config tay.
- Tự chọn góc đánh theo vị trí kho tài nguyên.
- Đóng gói Windows app bằng Electron/Tauri khi ổn định.
