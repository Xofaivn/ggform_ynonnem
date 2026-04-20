# Google Form Auto-Filler

Tự động điền và submit Google Forms nhiều lần với dữ liệu random có kiểm soát.

## Cài đặt

```bash
pip install selenium webdriver-manager openpyxl questionary rich
```

> Cần Chrome đã cài trên máy. `webdriver-manager` tự tải ChromeDriver phù hợp.

## Chạy

```bash
python main.py
```

Wizard sẽ hiện lên và hỏi từng bước cấu hình.

---

## Cấu trúc project

```
nem/
├── main.py              # Entry point
├── ui/
│   └── wizard.py        # Wizard khởi động (questionary + rich)
├── core/
│   ├── config.py        # RunConfig, KeywordRule, TextRule + profile I/O
│   ├── driver.py        # Chrome WebDriver + phát hiện ngôn ngữ form
│   ├── filler.py        # Vòng lặp điền form, xử lý đa trang
│   └── handlers.py      # Handler từng loại câu hỏi
├── utils/
│   └── elements.py      # Tiện ích DOM (get text, filter "Mục khác")
├── profiles/            # Config đã lưu (JSON), load lại lần sau
└── data/
    └── answers.txt      # Câu trả lời mẫu
```

---

## Wizard — các bước cấu hình

| # | Thiết lập | Mô tả |
|---|---|---|
| 1 | Form URL | Link Google Form (chứa `google.com/forms` hoặc `forms.gle`) |
| 2 | Số lần submit | Bao nhiêu lần điền |
| 3 | Headless | Ẩn cửa sổ Chrome hay hiện ra |
| 4 | Ngôn ngữ form | Auto / Tiếng Việt / English — ảnh hưởng phát hiện nút Next/Submit |
| 5 | Randomization level | 1 = luôn theo keyword, 5 = chủ yếu random |
| 6 | Hướng rating | Positive (ưu tiên 4–5), Negative (1–2), Neutral (đều) |
| 7 | Delay | Thời gian chờ giữa các lần submit (giây) |
| 8 | Preview mode | Không click Submit — chỉ điền để xem |
| 9 | Khoảng ngày | Ngẫu nhiên ngày trong khoảng cho câu hỏi Date |
| 10 | Keyword Rules | Ưu tiên đáp án theo keyword trong câu hỏi (radio/checkbox) |
| 11 | Text Rules | Đoạn văn paste vào câu hỏi tự luận theo keyword |

---

## Keyword Rules (chi tiết)

Dùng để ưu tiên chọn đáp án cụ thể cho câu hỏi trắc nghiệm.

**Ví dụ thực tế:**
- Form hỏi *"Bạn thường mua hàng ở kênh nào?"*
- Muốn ưu tiên chọn đáp án chứa "Online" hoặc "Shopee"

Cấu hình:
```
Question keyword : mua hàng
Preferred answers: Online, Shopee
Tỉ lệ           : 0.8   ← 80% theo keyword, 20% random
```

**Lưu ý:**
- Nhiều keyword khớp → rule được định nghĩa **trước** có ưu tiên cao hơn
- `Tỉ lệ = 1.0` → luôn chọn theo keyword (nếu tìm thấy đáp án khớp)
- `Tỉ lệ = 0.0` → không bao giờ dùng rule này
- Randomization level nhân thêm vào tỉ lệ (level 5 giảm ~70% xác suất áp dụng)

---

## Text Rules (chi tiết)

Dùng để paste đoạn văn cụ thể vào câu hỏi tự luận (short answer / paragraph).

**Ví dụ:**
- Form hỏi *"Bạn có nhận xét gì về sản phẩm?"*
- Muốn paste 1 trong 3 đoạn văn sẵn có

Cấu hình:
```
Question keyword: nhận xét
Đoạn 1: Sản phẩm rất tốt, tôi rất hài lòng.
Đoạn 2: Chất lượng ổn, giá cả hợp lý.
Đoạn 3: Sẽ giới thiệu cho bạn bè.
```
→ Mỗi submission random chọn 1 trong 3 đoạn trên.

---

## Profiles

Sau khi cấu hình xong, wizard hỏi có muốn lưu profile không. Profile lưu toàn bộ cài đặt (kể cả URL, keyword rules) vào `profiles/<tên>.json`. Lần sau chọn load profile thay vì nhập lại.

---

## Lưu ý kỹ thuật

- **"Mục khác" / "Other"** không bao giờ được chọn ở mọi loại câu hỏi
- **Grid questions** (nhiều câu rate 1–5 trong 1 bảng): chọn 1 đáp án cho **mỗi hàng**
- **Đa trang**: tự động nhấn "Tiếp tục" qua từng trang, nhấn "Gửi" ở trang cuối
- **Checkbox**: chọn ngẫu nhiên 1 đến (tổng/2 + 1) đáp án, ưu tiên keyword trước
