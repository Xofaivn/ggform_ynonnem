from __future__ import annotations

import random
import time
from datetime import date, timedelta

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

from core.config import RunConfig
from utils.elements import get_option_text, is_other_option, scroll_and_click


def _is_avoided(option: WebElement, config: RunConfig) -> bool:
    """Trả về True nếu option text khớp bất kỳ từ trong avoid_answers (global blacklist)."""
    if not config.avoid_answers:
        return False
    text = get_option_text(option).lower()
    return any(kw.lower() in text for kw in config.avoid_answers)


# ── Keyword matching helpers ──────────────────────────────────────────────────

def _match_keyword_option(label: str, options: list[WebElement], config: RunConfig) -> WebElement | None:
    """
    Duyệt keyword_rules theo thứ tự định nghĩa (ưu tiên rule đầu tiên).
    Trả về option khớp nếu rule được kích hoạt, ngược lại None.
    """
    label_lower = label.lower()
    for rule in config.keyword_rules:
        if rule.question_keyword.lower() not in label_lower:
            continue
        prob = config.keyword_apply_prob(rule.ratio)
        if random.random() >= prob:
            break  # rule này bị skip → không xét rule sau (ưu tiên thứ tự)
        matched = [
            o for o in options
            if any(p.lower() in get_option_text(o).lower() for p in rule.preferred_answers)
        ]
        if matched:
            return random.choice(matched)
        break
    return None


def _match_keyword_options_multi(label: str, options: list[WebElement], config: RunConfig) -> list[WebElement]:
    """
    Phiên bản cho checkbox: trả về danh sách tất cả option khớp keyword (không trùng).
    Ưu tiên rule đầu tiên khớp.
    """
    label_lower = label.lower()
    for rule in config.keyword_rules:
        if rule.question_keyword.lower() not in label_lower:
            continue
        prob = config.keyword_apply_prob(rule.ratio)
        if random.random() >= prob:
            break
        matched = [
            o for o in options
            if any(p.lower() in get_option_text(o).lower() for p in rule.preferred_answers)
        ]
        if matched:
            return matched
        break
    return []


def _find_text_answer(label: str, config: RunConfig) -> str | None:
    """Tìm câu trả lời text phù hợp theo TextRule (ưu tiên rule đầu tiên khớp)."""
    label_lower = label.lower()
    for rule in config.text_rules:
        if rule.question_keyword.lower() in label_lower:
            return random.choice(rule.answers) if rule.answers else None
    return None


# ── Rating direction helper ───────────────────────────────────────────────────

def _pick_by_rating_direction(cells: list[WebElement], direction: str) -> WebElement:
    """
    Chọn cell từ danh sách theo hướng rating.
    positive → ưu tiên 80% nửa cuối (4–5), negative → nửa đầu (1–2), neutral → đều.
    """
    n = len(cells)
    if n == 0:
        raise ValueError("No cells to pick from")

    if direction == "neutral" or n <= 2:
        return random.choice(cells)

    mid = n // 2
    if direction == "positive":
        high_pool = cells[mid:]
        low_pool = cells[:mid]
    else:  # negative
        high_pool = cells[:mid]
        low_pool = cells[mid:]

    return random.choice(high_pool if random.random() < 0.8 else low_pool)


# ── Question label helper ─────────────────────────────────────────────────────

def get_question_label(block: WebElement) -> str:
    for sel in ["div[role='heading']", ".M7eMe", "span[dir='auto']"]:
        try:
            el = block.find_element(By.CSS_SELECTOR, sel)
            t = (el.text or "").strip()
            if t:
                return t
        except Exception:
            pass
    return ""


# ── Fill functions ────────────────────────────────────────────────────────────

def fill_multiple_choice(block: WebElement, driver: WebDriver, config: RunConfig, label: str) -> str:
    options = block.find_elements(By.CSS_SELECTOR, "div[role='radio']")
    selectable = [o for o in options if not is_other_option(o) and not _is_avoided(o, config)]
    if not selectable:
        return "MC → không có option hợp lệ"

    chosen = _match_keyword_option(label, selectable, config)
    if chosen is None:
        chosen = random.choice(selectable)
        kw_note = "random"
    else:
        kw_note = "keyword"

    scroll_and_click(block, chosen, driver)
    return f"MC → '{get_option_text(chosen)}' [{kw_note}]"


def fill_checkbox(block: WebElement, driver: WebDriver, config: RunConfig, label: str) -> str:
    # Thử nhiều selector để lấy checkbox options
    options: list[WebElement] = []
    for sel in [
        "div[role='checkbox']",
        "label[data-answer-value]",
        "div[data-answer-value]",
        ".docssharedWizToggleLabeledControl",
    ]:
        options = block.find_elements(By.CSS_SELECTOR, sel)
        if options:
            break

    selectable = [o for o in options if not is_other_option(o) and not _is_avoided(o, config)]
    if not selectable:
        return "Checkbox → không có option hợp lệ"

    # Số lượng cần chọn: 1 đến tất cả, ưu tiên không chọn quá nửa
    n = random.randint(1, max(1, len(selectable) // 2 + 1))
    n = min(n, len(selectable))

    # Ưu tiên keyword matches trước, rồi random phần còn lại
    priority = _match_keyword_options_multi(label, selectable, config)
    chosen: list[WebElement] = list(priority[:n])
    remaining = [o for o in selectable if o not in chosen]
    random.shuffle(remaining)
    chosen += remaining[: n - len(chosen)]

    for opt in chosen:
        try:
            scroll_and_click(block, opt, driver)
            time.sleep(random.uniform(0.05, 0.15))
        except Exception:
            pass

    names = [get_option_text(o) for o in chosen]
    kw_note = f"{len(priority)} keyword + {len(chosen)-len(priority)} random" if priority else "random"
    return f"Checkbox → {names} [{kw_note}]"


def fill_dropdown(block: WebElement, driver: WebDriver, config: RunConfig, label: str) -> str:
    try:
        trigger = block.find_element(By.CSS_SELECTOR, "div[role='listbox']")
        scroll_and_click(block, trigger, driver)
        time.sleep(0.4)
        options = driver.find_elements(By.CSS_SELECTOR, "div[role='option']")
        selectable = [o for o in options if not is_other_option(o) and not _is_avoided(o, config) and get_option_text(o)]
        if not selectable:
            return "Dropdown → không có option"

        chosen = _match_keyword_option(label, selectable, config)
        if chosen is None:
            chosen = random.choice(selectable)
            kw_note = "random"
        else:
            kw_note = "keyword"

        scroll_and_click(block, chosen, driver)
        return f"Dropdown → '{get_option_text(chosen)}' [{kw_note}]"
    except Exception as e:
        return f"Dropdown lỗi: {e}"


def fill_linear_scale(block: WebElement, driver: WebDriver, config: RunConfig, label: str) -> str:
    cells = block.find_elements(By.CSS_SELECTOR, "div[role='radio']")
    if not cells:
        return "Scale → không tìm được cell"

    chosen = _pick_by_rating_direction(cells, config.rating_direction)
    scroll_and_click(block, chosen, driver)
    idx = cells.index(chosen) + 1
    return f"Scale → {idx}/{len(cells)} [{config.rating_direction}]"


def fill_grid(block: WebElement, driver: WebDriver, config: RunConfig, label: str) -> str:
    """
    Điền grid (matrix): chọn 1 ô cho MỖI hàng.
    Hỗ trợ cả radio grid lẫn checkbox grid.
    """
    # Thứ tự ưu tiên selectors cho hàng dữ liệu:
    # 1. div[role='radiogroup'] — Google Forms hiện đại (mỗi hàng là 1 radiogroup)
    # 2. tr[role='row'] — table-based grid
    # 3. div[role='row'] — div-based grid (bỏ hàng header không có radio)
    # 4. <tr> có <td> — fallback table
    rows: list[WebElement] = block.find_elements(By.CSS_SELECTOR, "div[role='radiogroup']")
    if not rows:
        rows = block.find_elements(By.CSS_SELECTOR, "tr[role='row']")
    if not rows:
        rows = block.find_elements(By.CSS_SELECTOR, "div[role='row']")
    if not rows:
        all_rows = block.find_elements(By.CSS_SELECTOR, "tr")
        rows = [r for r in all_rows if r.find_elements(By.CSS_SELECTOR, "td")]

    # Lọc bỏ hàng header (không chứa radio/checkbox)
    rows = [r for r in rows if r.find_elements(By.CSS_SELECTOR, "div[role='radio'], div[role='checkbox']")]

    if not rows:
        return "Grid → không tìm được hàng"

    filled = 0
    errors = 0
    for row in rows:
        cells = row.find_elements(By.CSS_SELECTOR, "div[role='radio']")
        if not cells:
            cells = row.find_elements(By.CSS_SELECTOR, "div[role='checkbox']")
        if not cells:
            continue
        cells = [c for c in cells if not _is_avoided(c, config)]
        if not cells:
            continue

        chosen = _pick_by_rating_direction(cells, config.rating_direction)
        try:
            scroll_and_click(block, chosen, driver)
            time.sleep(random.uniform(0.08, 0.2))
            filled += 1
        except Exception as e:
            errors += 1

    suffix = f" ({errors} lỗi click)" if errors else ""
    return f"Grid → {filled}/{len(rows)} hàng [{config.rating_direction}]{suffix}"


def fill_short_answer(block: WebElement, driver: WebDriver, config: RunConfig, label: str) -> str:
    answer = _find_text_answer(label, config)
    if answer is None:
        return "Short answer → bỏ trống (không có data)"

    try:
        inp = block.find_element(By.CSS_SELECTOR, "input[type='text']")
        inp.clear()
        inp.send_keys(answer)
        return f"Short answer → '{answer[:40]}'"
    except Exception as e:
        return f"Short answer lỗi: {e}"


def fill_paragraph(block: WebElement, driver: WebDriver, config: RunConfig, label: str) -> str:
    answer = _find_text_answer(label, config)
    if answer is None:
        return "Paragraph → bỏ trống (không có data)"

    try:
        ta = block.find_element(By.CSS_SELECTOR, "textarea")
        ta.clear()
        ta.send_keys(answer)
        return f"Paragraph → '{answer[:40]}'"
    except Exception as e:
        return f"Paragraph lỗi: {e}"


def fill_date(block: WebElement, driver: WebDriver, config: RunConfig, label: str) -> str:
    """Điền ngày ngẫu nhiên trong khoảng [date_start, date_end]."""
    try:
        start = date.fromisoformat(config.date_start)
        end = date.fromisoformat(config.date_end)
        delta = (end - start).days
        if delta < 0:
            start, end = end, start
            delta = -delta
        chosen_date = start + timedelta(days=random.randint(0, delta))

        # Google Forms dùng input[type='date'] hoặc 3 input riêng (day/month/year)
        inputs = block.find_elements(By.CSS_SELECTOR, "input[type='date']")
        if inputs:
            driver.execute_script(
                "arguments[0].value = arguments[1];",
                inputs[0],
                chosen_date.isoformat(),
            )
            return f"Date → {chosen_date.isoformat()}"

        # Thử 3 input riêng: day, month, year
        parts = block.find_elements(By.CSS_SELECTOR, "input[type='number'], input[aria-label]")
        if len(parts) >= 3:
            parts[0].clear(); parts[0].send_keys(str(chosen_date.month))
            parts[1].clear(); parts[1].send_keys(str(chosen_date.day))
            parts[2].clear(); parts[2].send_keys(str(chosen_date.year))
            return f"Date → {chosen_date.isoformat()}"

        return "Date → không tìm được input"
    except Exception as e:
        return f"Date lỗi: {e}"


# ── Detect question type & dispatch ──────────────────────────────────────────

def detect_and_fill(block: WebElement, driver: WebDriver, config: RunConfig) -> str:
    """Phát hiện loại câu hỏi trong block và gọi handler phù hợp."""
    label = get_question_label(block)

    try:
        # --- Checkbox (phải check trước radio vì grid có thể chứa cả hai)
        checkboxes = block.find_elements(By.CSS_SELECTOR, "div[role='checkbox']")
        # Check nếu đây là grid:
        # - có table/tr[role='row']/div[role='row'] (grid cũ)
        # - hoặc có nhiều div[role='radiogroup'] (Google Forms hiện đại: mỗi hàng = 1 radiogroup)
        radiogroups = block.find_elements(By.CSS_SELECTOR, "div[role='radiogroup']")
        is_grid_structure = bool(
            block.find_elements(By.CSS_SELECTOR, "table")
            or block.find_elements(By.CSS_SELECTOR, "tr[role='row']")
            or block.find_elements(By.CSS_SELECTOR, "div[role='row']")
            or len(radiogroups) > 1
        )

        if is_grid_structure:
            return f"[Grid] {label[:50]} → {fill_grid(block, driver, config, label)}"

        # --- Linear scale (radio nhưng không có heading row → scale 1-N)
        radios = block.find_elements(By.CSS_SELECTOR, "div[role='radio']")
        if radios:
            # Phân biệt scale với MC: scale thường có nhiều radio và không có text dài
            texts = [get_option_text(r) for r in radios]
            all_numeric = all(t.strip().lstrip("-").isdigit() or t == "" for t in texts)
            if all_numeric and len(radios) >= 3:
                return f"[Scale] {label[:50]} → {fill_linear_scale(block, driver, config, label)}"
            return f"[MC] {label[:50]} → {fill_multiple_choice(block, driver, config, label)}"

        if checkboxes:
            return f"[Checkbox] {label[:50]} → {fill_checkbox(block, driver, config, label)}"

        # --- Dropdown
        if block.find_elements(By.CSS_SELECTOR, "div[role='listbox']"):
            return f"[Dropdown] {label[:50]} → {fill_dropdown(block, driver, config, label)}"

        # --- Date
        if block.find_elements(By.CSS_SELECTOR, "input[type='date']"):
            return f"[Date] {label[:50]} → {fill_date(block, driver, config, label)}"

        # --- Paragraph
        if block.find_elements(By.CSS_SELECTOR, "textarea"):
            return f"[Para] {label[:50]} → {fill_paragraph(block, driver, config, label)}"

        # --- Short answer
        if block.find_elements(By.CSS_SELECTOR, "input[type='text']"):
            return f"[Text] {label[:50]} → {fill_short_answer(block, driver, config, label)}"

        return f"[?] {label[:50]} → không nhận dạng được loại câu hỏi"

    except Exception as e:
        return f"[ERR] {label[:50]} → {e}"
