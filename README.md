# COC Auto Farm LDPlayer 1600x900

Tool auto farm làng chính qua ADB, có GUI chỉnh ngưỡng tài nguyên, chế độ thả, điều kiện đầu hàng và log.

## Chạy

```powershell
python -m pip install -r requirements.txt
python main.py
```

Nếu GUI báo không thấy `adb.exe`, điền đường dẫn ADB vào `config.json` tại:

```json
"adb": {
  "path": "C:/duong/dan/toi/adb.exe",
  "device": "127.0.0.1:5555"
}
```

OCR cần Tesseract. Nếu máy chưa có, cài Tesseract OCR rồi điền `ocr.tesseract_path` nếu tool không tự nhận.

## Flow

`Home -> Attack -> Find a Match -> My Army Attack -> đọc loot -> Next/đánh -> theo dõi đầu hàng -> Return Home -> lặp`
