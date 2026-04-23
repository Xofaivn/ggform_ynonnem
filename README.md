# Google Form Auto-Filler

Tự động điền và submit Google Forms nhiều lần với dữ liệu random có kiểm soát.

Hai chế độ: **Terminal wizard** và **Web UI** (giao diện trên browser).

---

## Cài đặt

```bash
pip install selenium webdriver-manager openpyxl questionary rich fastapi "uvicorn[standard]"
```

> Cần Chrome đã cài trên máy. `webdriver-manager` tự tải ChromeDriver phù hợp, không cần cài tay.

Khuyến nghị dùng virtual environment:

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install selenium webdriver-manager openpyxl questionary rich fastapi "uvicorn[standard]"
```

> `.venv/` đã có trong `.gitignore` — không được push lên Git.

---

## Chạy

### Web UI (khuyên dùng)

```bash
python web_main.py
```

Mở trình duyệt → `http://localhost:8000`

Giao diện nền đêm sao băng, card glassmorphism với 3 tab:
- **Config** — cấu hình + nút Bắt đầu/Dừng + live log
- **Profiles** — quản lý profile đã lưu
- **History** — lịch sử các lần chạy trong session

### Terminal (wizard)

```bash
python main.py
```

Wizard hỏi từng bước cấu hình trên terminal.

### Docker

```bash
docker build -t form-filler .
docker run -p 8000:8000 form-filler
# → http://localhost:8000
```

---

## Cấu trúc project

```
nem/
├── main.py              # Entry point terminal
├── web_main.py          # Entry point web (uvicorn)
├── ui/
│   └── wizard.py        # Wizard terminal (questionary + rich)
├── core/
│   ├── config.py        # RunConfig, KeywordRule, TextRule + profile I/O
│   ├── driver.py        # Chrome WebDriver + phát hiện ngôn ngữ form
│   ├── filler.py        # Vòng lặp điền form, xử lý đa trang
│   └── handlers.py      # Handler từng loại câu hỏi
├── utils/
│   └── elements.py      # Tiện ích DOM (get text, filter "Mục khác")
├── web/
│   ├── app.py           # FastAPI: session, API, SSE streaming
│   └── static/
│       ├── index.html   # SPA
│       ├── style.css    # Glassmorphism + meteor rain
│       └── app.js       # Canvas animation + logic frontend
├── profiles/            # Config đã lưu (JSON)
└── data/
    └── answers.txt      # Câu trả lời mẫu
```

---

## Cấu hình

| Thiết lập | Mô tả |
|---|---|
| Form URL | Link Google Form |
| Số lần submit | Bao nhiêu lần điền |
| Headless | Ẩn cửa sổ Chrome hay hiện ra |
| Ngôn ngữ form | Auto / Tiếng Việt / English |
| Randomization level | 1 = luôn theo keyword, 5 = chủ yếu random |
| Hướng rating | Positive (ưu tiên 4–5), Negative (1–2), Neutral (đều) |
| Delay | Thời gian chờ giữa các lần submit (giây) |
| Preview mode | Không click Submit — chỉ điền để xem |
| Khoảng ngày | Ngẫu nhiên ngày trong khoảng cho câu hỏi Date |
| Keyword Rules | Ưu tiên đáp án theo keyword câu hỏi (radio/checkbox) |
| Text Rules | Đoạn văn cho câu hỏi tự luận theo keyword |
| Né đáp án | Danh sách keyword không bao giờ được chọn |

---

## Keyword Rules

Ưu tiên chọn đáp án cụ thể cho câu hỏi trắc nghiệm.

**Ví dụ:** Form hỏi *"Bạn thường mua hàng ở kênh nào?"*, muốn ưu tiên "Online" hoặc "Shopee":

```
Question keyword : mua hàng
Preferred answers: Online, Shopee
Tỉ lệ           : 0.8   ← 80% theo keyword, 20% random
```

- Nhiều keyword khớp → rule định nghĩa **trước** có ưu tiên hơn
- `Tỉ lệ = 1.0` → luôn chọn theo keyword
- Randomization level ảnh hưởng thêm vào tỉ lệ

---

## Text Rules

Paste đoạn văn cụ thể vào câu hỏi tự luận.

```
Question keyword: nhận xét
Đoạn 1: Sản phẩm rất tốt, tôi rất hài lòng.
---
Đoạn 2: Chất lượng ổn, giá cả hợp lý.
---
Đoạn 3: Sẽ giới thiệu cho bạn bè.
```

Mỗi submission random chọn 1 đoạn.

---

## Né đáp án

Danh sách keyword cách nhau bằng dấu phẩy. Mọi đáp án chứa keyword này sẽ không bao giờ được chọn.

```
không biết, chưa sử dụng, không có ý kiến
```

---

## Profiles

Lưu toàn bộ cài đặt vào `profiles/<tên>.json`. Lần sau load lại thay vì nhập lại từ đầu.

---

## Lưu ý kỹ thuật

- **"Mục khác" / "Other"** không bao giờ được chọn ở mọi loại câu hỏi
- **Grid questions**: chọn 1 đáp án cho **mỗi hàng**
- **Đa trang**: tự động nhấn "Tiếp" qua từng trang, nhấn "Gửi" ở trang cuối
- **Multi-user web**: mỗi tab browser có session riêng, chạy độc lập song song
