# Google Form Auto-Filler

Tool tự động điền và submit Google Forms nhiều lần với dữ liệu random có kiểm soát.

Hiện có 2 chế độ:
- `main.py`: terminal wizard
- `web_main.py`: web UI với login, quota, admin panel

## Tính năng chính

- Tự điền nhiều loại câu hỏi Google Forms
- Keyword rules và text rules
- Né đáp án blacklist toàn cục
- Tự bỏ qua các đáp án kiểu `Kết thúc khảo sát`
- Retry tối đa 3 lần nếu Chrome hoặc lượt submit bị lỗi
- Login `user/admin` bằng JWT
- Admin quản lý user và quota
- Mỗi submit thành công sẽ trừ quota của user thường
- Progress bar, browser notification, ding khi chạy xong

## Cài đặt local

Khuyên dùng virtual environment:

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

Cần có Chrome trên máy. `webdriver-manager` sẽ tự lấy ChromeDriver phù hợp.

## Cấu hình môi trường

Tạo file `.env` từ `.env.example` hoặc set env trực tiếp:

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/formfiller
JWT_SECRET=changeme
DB_CONNECT_RETRIES=10
DB_CONNECT_DELAY=1.5
```

## Chạy PostgreSQL

### Cách 1: Docker Compose

```bash
docker compose up --build
```

Sau đó mở:

```text
http://localhost:8000
```

Compose hiện dựng luôn:
- `postgres` trên cổng `5432`
- `app` trên cổng `8000`

### Cách 2: PostgreSQL có sẵn trên máy

Chỉ cần đảm bảo `DATABASE_URL` trỏ tới database PostgreSQL hợp lệ, rồi chạy:

```bash
python web_main.py
```

## Tài khoản mặc định

Khi server start và bảng `users` đang rỗng, app sẽ seed:

```text
username: admin
password: admin1
```

## Chạy app

### Web UI

```bash
python web_main.py
```

Mở `http://localhost:8000`

Các màn chính:
- `Config`: cấu hình chạy form, live log, progress bar
- `Profiles`: lưu và load profile JSON
- `History`: lịch sử chạy của session hiện tại
- `Admin`: chỉ hiện với admin, dùng để tạo user, tìm user, đổi quota, xóa user

### Terminal wizard

```bash
python main.py
```

## Docker

Nếu không dùng compose, vẫn có thể build riêng app:

```bash
docker build -t form-filler .
docker run -p 8000:8000 \
  -e DATABASE_URL=postgresql://postgres:postgres@host.docker.internal:5432/formfiller \
  -e JWT_SECRET=changeme \
  form-filler
```

Lưu ý: container app không tự chứa PostgreSQL. Dùng `docker-compose.yml` là cách đầy đủ hơn.

## API chính

- `GET /api/health`
- `POST /api/auth/login`
- `GET /api/me`
- `POST /api/session`
- `GET /api/status/{sid}`
- `POST /api/run/{sid}`
- `POST /api/stop/{sid}`
- `GET /api/history/{sid}`
- `GET /api/profiles`
- `GET /api/profiles/{name}`
- `POST /api/profiles/{name}`
- `DELETE /api/profiles/{name}`
- `GET /api/admin/users`
- `POST /api/admin/users`
- `PUT /api/admin/users/{uid}`
- `DELETE /api/admin/users/{uid}`

## Quota

- Admin có `quota_remaining = NULL`, tức không giới hạn
- User thường bị trừ `1` quota sau mỗi submit thành công
- Nếu user yêu cầu chạy nhiều hơn quota còn lại, app tự giảm `n_submissions`
- Nếu quota đã hết, app chặn chạy từ backend và disable nút start ở frontend

## Kiểm tra nhanh

1. Start PostgreSQL
2. Chạy `python web_main.py` hoặc `docker compose up --build`
3. Mở `http://localhost:8000`
4. Login bằng `admin/admin1`
5. Vào tab `Admin`, tạo user mới với quota nhỏ, ví dụ `5`
6. Logout rồi login bằng user vừa tạo
7. Chạy form nhiều lần để xác nhận quota bị trừ

## Cấu trúc project

```text
nem/
├── core/
│   ├── config.py
│   ├── driver.py
│   ├── filler.py
│   └── handlers.py
├── ui/
│   └── wizard.py
├── utils/
│   └── elements.py
├── web/
│   ├── app.py
│   ├── auth.py
│   ├── db.py
│   └── static/
│       ├── app.js
│       ├── index.html
│       └── style.css
├── profiles/
├── Dockerfile
├── docker-compose.yml
├── main.py
├── requirements.txt
└── web_main.py
```
