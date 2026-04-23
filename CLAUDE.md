# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Google Forms auto-filler. Hai chế độ chạy: **Terminal wizard** (`python main.py`) và **Web UI** (`python web_main.py` → `localhost:8000`).

## Setup & Run

```bash
# Setup virtual environment (khuyến nghị)
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux
pip install selenium webdriver-manager openpyxl questionary rich fastapi "uvicorn[standard]"

# Terminal mode
python main.py

# Web mode
python web_main.py
# → http://localhost:8000

# Docker
docker build -t form-filler .
docker run -p 8000:8000 form-filler
```

`.venv/`, `profiles/`, `data/`, `__pycache__/` đã có trong `.gitignore`.

Không có test framework. Validate bằng cách chạy với 1 lần submit và `headless=False` để quan sát Chrome.

## Project Structure

```
nem/
├── main.py                  # Entry point terminal mode
├── web_main.py              # Entry point web mode (uvicorn)
├── ui/
│   └── wizard.py            # Interactive startup wizard (questionary + rich)
├── core/
│   ├── config.py            # RunConfig, KeywordRule, TextRule dataclasses + profile I/O
│   ├── driver.py            # Chrome WebDriver factory + detect_form_language()
│   ├── filler.py            # fill_form_once(), run_all() — vòng lặp submission
│   └── handlers.py          # Handlers từng loại câu hỏi + keyword/rating helpers
├── utils/
│   └── elements.py          # get_option_text(), is_other_option(), scroll_and_click()
├── web/
│   ├── __init__.py
│   ├── app.py               # FastAPI app: session mgmt, REST API, SSE streaming
│   └── static/
│       ├── index.html       # Single-page app (3 tabs: Config, Profiles, History)
│       ├── style.css        # Glassmorphism card + meteor rain background
│       └── app.js           # Canvas meteor animation + full SPA logic
├── profiles/                # JSON profiles lưu RunConfig
├── data/
│   └── answers.txt          # Sample text answers
├── Dockerfile
└── requirements.txt
```

## Architecture

### Dual-mode RunConfig flow
```
Terminal:  main.py → run_wizard() → RunConfig → run_all(config)
Web:       Browser → POST /api/run/{sid} → Thread(run_all(config, log_fn, stop_event, driver_ref))
                                                    ↓
                     GET /api/stream/{sid} ← SSE queue ← log_fn callbacks
```

### `run_all()` signature
```python
run_all(config: RunConfig, log_fn=None, stop_event=None, driver_ref=None) -> dict
# Returns {"success": N, "fail": N}
# log_fn=None → defaults to console.print (terminal mode unchanged)
# stop_event: threading.Event — set() to interrupt mid-run
# driver_ref: list[WebDriver] — allows external quit
```

### Web session model (`web/app.py`)
`SessionState` dataclass stored in `sessions: dict[str, SessionState]` (in-memory, no DB). Each browser tab gets a UUID `sid` stored in `localStorage`. Sessions are created on first `POST /api/session`.

### API routes
```
POST /api/session            → create/return session
POST /api/run/{sid}          → start automation (body = RunConfig JSON)
GET  /api/stream/{sid}       → SSE log stream
POST /api/stop/{sid}         → stop_event.set() + driver.quit()
GET  /api/status/{sid}       → {status, progress}
GET  /api/history/{sid}      → run history
GET/POST/DELETE /api/profiles/{name}
GET  /                       → index.html
```

SSE keepalive: `yield ": keepalive\n\n"` on empty queue to prevent browser timeout.

### Question type detection (`core/handlers.py : detect_and_fill`)
Thứ tự ưu tiên: Grid (`div[role='radiogroup']` count > 1) → Linear Scale (radio toàn số) → Multiple Choice (radio) → Checkbox → Dropdown → Date → Paragraph → Short Answer.

### Grid row detection (`fill_grid`)
Priority order: `div[role='radiogroup']` (modern Google Forms) → `tr[role='row']` → `div[role='row']` → `tr` with `td` children. Always filter rows to only those containing `div[role='radio']` or `div[role='checkbox']` to exclude header rows.

### Keyword matching
- **KeywordRule**: radio/checkbox — khớp label câu hỏi → ưu tiên chọn đáp án chứa preferred text. Rule đầu tiên khớp thắng. `randomization_level` (1–5) nhân với `ratio` để tính xác suất.
- **TextRule**: paragraph/short answer — khớp label → random chọn 1 trong pool đoạn văn.
- **avoid_answers**: blacklist — bất kỳ option nào chứa keyword bị loại trước khi chọn (`_is_avoided()` trong handlers.py).

### Rating direction
`_pick_by_rating_direction()` cho `fill_linear_scale` và `fill_grid`:
- `positive` → 80% chọn nửa cuối (điểm cao)
- `negative` → 80% chọn nửa đầu (điểm thấp)
- `neutral` → random đều

### Multi-page navigation (`core/filler.py`)
`_classify_buttons()` tries `[jsname='P2WeLd']` first (Google Forms primary action), then XPath fallback excluding `ancestor::div[@data-params]` (question-block buttons). `_btn_text()` applies `unicodedata.normalize("NFC", s)` for reliable Vietnamese comparison. After click Next: wait via `EC.staleness_of(anchor)` — không dùng `find_elements` để wait (trả về element cũ).

### Frontend log rendering (`web/static/app.js`)
`richToHtml(text)` converts Rich markup (`[bold]`, `[green]`, `[red]`, etc.) to HTML spans with CSS color classes. Auto-scroll log panel on new entries.

## Key Invariants
- `is_other_option()` phải gọi trước mọi `random.choice()` trên options.
- `_is_avoided()` phải gọi sau `is_other_option()` filter.
- Keyword rule đầu tiên khớp thắng — thứ tự trong `config.keyword_rules` là ưu tiên.
- `RunConfig` không có `checkbox_min/max` — số lượng checkbox tự tính `randint(1, len//2+1)`.
- Terminal mode (`main.py`) không thay đổi behavior — `run_all()` không có `log_fn` defaults to `console.print`.
