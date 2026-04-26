from __future__ import annotations

import random
import time
from datetime import date, timedelta

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

from core.config import RunConfig
from utils.elements import get_option_text, is_other_option, scroll_and_click

_END_SURVEY_PATTERNS = [
    "kết thúc khảo sát",
    "(kết thúc)",
    "end survey",
    "end of survey",
    "không tham gia",
    "không tiếp tục khảo sát",
]


def _is_avoided(option: WebElement | str, config: RunConfig) -> bool:
    """Return True when an option should always be skipped."""
    text = option if isinstance(option, str) else get_option_text(option)
    text = text.lower()
    if any(pattern in text for pattern in _END_SURVEY_PATTERNS):
        return True
    if not config.avoid_answers:
        return False
    return any(keyword.lower() in text for keyword in config.avoid_answers)


def _match_keyword_option(
    label: str,
    options: list[WebElement],
    config: RunConfig,
) -> WebElement | None:
    label_lower = label.lower()
    for rule in config.keyword_rules:
        if rule.question_keyword.lower() not in label_lower:
            continue
        probability = config.keyword_apply_prob(rule.ratio)
        if random.random() >= probability:
            break
        matched = [
            option
            for option in options
            if any(
                preferred.lower() in get_option_text(option).lower()
                for preferred in rule.preferred_answers
            )
        ]
        if matched:
            return random.choice(matched)
        break
    return None


def _match_keyword_options_multi(
    label: str,
    options: list[WebElement],
    config: RunConfig,
) -> list[WebElement]:
    label_lower = label.lower()
    for rule in config.keyword_rules:
        if rule.question_keyword.lower() not in label_lower:
            continue
        probability = config.keyword_apply_prob(rule.ratio)
        if random.random() >= probability:
            break
        matched = [
            option
            for option in options
            if any(
                preferred.lower() in get_option_text(option).lower()
                for preferred in rule.preferred_answers
            )
        ]
        if matched:
            return matched
        break
    return []


def _find_text_answer(label: str, config: RunConfig) -> str | None:
    label_lower = label.lower()
    for rule in config.text_rules:
        if rule.question_keyword.lower() in label_lower:
            return random.choice(rule.answers) if rule.answers else None
    return None


def _pick_by_rating_direction(cells: list[WebElement], direction: str) -> WebElement:
    count = len(cells)
    if count == 0:
        raise ValueError("No cells to pick from")

    if direction == "neutral" or count <= 2:
        return random.choice(cells)

    mid = count // 2
    if direction == "positive":
        preferred_pool = cells[mid:]
        secondary_pool = cells[:mid]
    else:
        preferred_pool = cells[:mid]
        secondary_pool = cells[mid:]

    pool = preferred_pool if random.random() < 0.8 else secondary_pool
    return random.choice(pool)


def get_question_label(block: WebElement) -> str:
    for selector in ["div[role='heading']", ".M7eMe", "span[dir='auto']"]:
        try:
            element = block.find_element(By.CSS_SELECTOR, selector)
            text = (element.text or "").strip()
            if text:
                return text
        except Exception:
            pass
    return ""


def fill_multiple_choice(
    block: WebElement,
    driver: WebDriver,
    config: RunConfig,
    label: str,
) -> str:
    options = block.find_elements(By.CSS_SELECTOR, "div[role='radio']")
    selectable = [
        option
        for option in options
        if not is_other_option(option) and not _is_avoided(option, config)
    ]
    if not selectable:
        return "MC -> không có option hợp lệ"

    chosen = _match_keyword_option(label, selectable, config)
    if chosen is None:
        chosen = random.choice(selectable)
        mode = "random"
    else:
        mode = "keyword"

    scroll_and_click(block, chosen, driver)
    return f"MC -> '{get_option_text(chosen)}' [{mode}]"


def fill_checkbox(
    block: WebElement,
    driver: WebDriver,
    config: RunConfig,
    label: str,
) -> str:
    options: list[WebElement] = []
    for selector in [
        "div[role='checkbox']",
        "label[data-answer-value]",
        "div[data-answer-value]",
        ".docssharedWizToggleLabeledControl",
    ]:
        options = block.find_elements(By.CSS_SELECTOR, selector)
        if options:
            break

    selectable = [
        option
        for option in options
        if not is_other_option(option) and not _is_avoided(option, config)
    ]
    if not selectable:
        return "Checkbox -> không có option hợp lệ"

    limit = random.randint(1, max(1, len(selectable) // 2 + 1))
    limit = min(limit, len(selectable))

    priority = _match_keyword_options_multi(label, selectable, config)
    chosen: list[WebElement] = list(priority[:limit])
    remaining = [option for option in selectable if option not in chosen]
    random.shuffle(remaining)
    chosen += remaining[: limit - len(chosen)]

    for option in chosen:
        try:
            scroll_and_click(block, option, driver)
            time.sleep(random.uniform(0.05, 0.15))
        except Exception:
            pass

    names = [get_option_text(option) for option in chosen]
    mode = f"{len(priority)} keyword + {len(chosen) - len(priority)} random" if priority else "random"
    return f"Checkbox -> {names} [{mode}]"


def fill_dropdown(
    block: WebElement,
    driver: WebDriver,
    config: RunConfig,
    label: str,
) -> str:
    try:
        trigger = block.find_element(By.CSS_SELECTOR, "div[role='listbox']")
        scroll_and_click(block, trigger, driver)
        time.sleep(0.4)
        options = driver.find_elements(By.CSS_SELECTOR, "div[role='option']")
        selectable = [
            option
            for option in options
            if not is_other_option(option)
            and not _is_avoided(option, config)
            and get_option_text(option)
        ]
        if not selectable:
            return "Dropdown -> không có option"

        chosen = _match_keyword_option(label, selectable, config)
        if chosen is None:
            chosen = random.choice(selectable)
            mode = "random"
        else:
            mode = "keyword"

        scroll_and_click(block, chosen, driver)
        return f"Dropdown -> '{get_option_text(chosen)}' [{mode}]"
    except Exception as exc:
        return f"Dropdown lỗi: {exc}"


def fill_linear_scale(
    block: WebElement,
    driver: WebDriver,
    config: RunConfig,
    label: str,
) -> str:
    cells = block.find_elements(By.CSS_SELECTOR, "div[role='radio']")
    if not cells:
        return "Scale -> không tìm được cell"

    chosen = _pick_by_rating_direction(cells, config.rating_direction)
    scroll_and_click(block, chosen, driver)
    idx = cells.index(chosen) + 1
    return f"Scale -> {idx}/{len(cells)} [{config.rating_direction}]"


def fill_grid(
    block: WebElement,
    driver: WebDriver,
    config: RunConfig,
    label: str,
) -> str:
    rows: list[WebElement] = block.find_elements(By.CSS_SELECTOR, "div[role='radiogroup']")
    if not rows:
        rows = block.find_elements(By.CSS_SELECTOR, "tr[role='row']")
    if not rows:
        rows = block.find_elements(By.CSS_SELECTOR, "div[role='row']")
    if not rows:
        all_rows = block.find_elements(By.CSS_SELECTOR, "tr")
        rows = [row for row in all_rows if row.find_elements(By.CSS_SELECTOR, "td")]

    rows = [
        row
        for row in rows
        if row.find_elements(By.CSS_SELECTOR, "div[role='radio'], div[role='checkbox']")
    ]
    if not rows:
        return "Grid -> không tìm được hàng"

    filled = 0
    errors = 0
    for row in rows:
        cells = row.find_elements(By.CSS_SELECTOR, "div[role='radio']")
        if not cells:
            cells = row.find_elements(By.CSS_SELECTOR, "div[role='checkbox']")
        cells = [cell for cell in cells if not _is_avoided(cell, config)]
        if not cells:
            continue

        chosen = _pick_by_rating_direction(cells, config.rating_direction)
        try:
            scroll_and_click(block, chosen, driver)
            time.sleep(random.uniform(0.08, 0.2))
            filled += 1
        except Exception:
            errors += 1

    suffix = f" ({errors} lỗi click)" if errors else ""
    return f"Grid -> {filled}/{len(rows)} hàng [{config.rating_direction}]{suffix}"


def fill_short_answer(
    block: WebElement,
    driver: WebDriver,
    config: RunConfig,
    label: str,
) -> str:
    answer = _find_text_answer(label, config)
    if answer is None:
        return "Short answer -> bỏ trống (không có data)"

    try:
        input_el = block.find_element(By.CSS_SELECTOR, "input[type='text']")
        input_el.clear()
        input_el.send_keys(answer)
        return f"Short answer -> '{answer[:40]}'"
    except Exception as exc:
        return f"Short answer lỗi: {exc}"


def fill_paragraph(
    block: WebElement,
    driver: WebDriver,
    config: RunConfig,
    label: str,
) -> str:
    answer = _find_text_answer(label, config)
    if answer is None:
        return "Paragraph -> bỏ trống (không có data)"

    try:
        textarea = block.find_element(By.CSS_SELECTOR, "textarea")
        textarea.clear()
        textarea.send_keys(answer)
        return f"Paragraph -> '{answer[:40]}'"
    except Exception as exc:
        return f"Paragraph lỗi: {exc}"


def fill_date(
    block: WebElement,
    driver: WebDriver,
    config: RunConfig,
    label: str,
) -> str:
    try:
        start = date.fromisoformat(config.date_start)
        end = date.fromisoformat(config.date_end)
        delta = (end - start).days
        if delta < 0:
            start, end = end, start
            delta = -delta
        chosen_date = start + timedelta(days=random.randint(0, delta))

        inputs = block.find_elements(By.CSS_SELECTOR, "input[type='date']")
        if inputs:
            driver.execute_script(
                "arguments[0].value = arguments[1];",
                inputs[0],
                chosen_date.isoformat(),
            )
            return f"Date -> {chosen_date.isoformat()}"

        parts = block.find_elements(By.CSS_SELECTOR, "input[type='number'], input[aria-label]")
        if len(parts) >= 3:
            parts[0].clear()
            parts[0].send_keys(str(chosen_date.month))
            parts[1].clear()
            parts[1].send_keys(str(chosen_date.day))
            parts[2].clear()
            parts[2].send_keys(str(chosen_date.year))
            return f"Date -> {chosen_date.isoformat()}"

        return "Date -> không tìm được input"
    except Exception as exc:
        return f"Date lỗi: {exc}"


def detect_and_fill(block: WebElement, driver: WebDriver, config: RunConfig) -> str:
    label = get_question_label(block)

    try:
        checkboxes = block.find_elements(By.CSS_SELECTOR, "div[role='checkbox']")
        radiogroups = block.find_elements(By.CSS_SELECTOR, "div[role='radiogroup']")
        is_grid_structure = bool(
            block.find_elements(By.CSS_SELECTOR, "table")
            or block.find_elements(By.CSS_SELECTOR, "tr[role='row']")
            or block.find_elements(By.CSS_SELECTOR, "div[role='row']")
            or len(radiogroups) > 1
        )

        if is_grid_structure:
            return f"[Grid] {label[:50]} -> {fill_grid(block, driver, config, label)}"

        radios = block.find_elements(By.CSS_SELECTOR, "div[role='radio']")
        if radios:
            texts = [get_option_text(radio) for radio in radios]
            all_numeric = all(text.strip().lstrip("-").isdigit() or text == "" for text in texts)
            if all_numeric and len(radios) >= 3:
                return f"[Scale] {label[:50]} -> {fill_linear_scale(block, driver, config, label)}"
            return f"[MC] {label[:50]} -> {fill_multiple_choice(block, driver, config, label)}"

        if checkboxes:
            return f"[Checkbox] {label[:50]} -> {fill_checkbox(block, driver, config, label)}"

        if block.find_elements(By.CSS_SELECTOR, "div[role='listbox']"):
            return f"[Dropdown] {label[:50]} -> {fill_dropdown(block, driver, config, label)}"

        if block.find_elements(By.CSS_SELECTOR, "input[type='date']"):
            return f"[Date] {label[:50]} -> {fill_date(block, driver, config, label)}"

        if block.find_elements(By.CSS_SELECTOR, "textarea"):
            return f"[Para] {label[:50]} -> {fill_paragraph(block, driver, config, label)}"

        if block.find_elements(By.CSS_SELECTOR, "input[type='text']"):
            return f"[Text] {label[:50]} -> {fill_short_answer(block, driver, config, label)}"

        return f"[?] {label[:50]} -> không nhận dạng được loại câu hỏi"
    except Exception as exc:
        return f"[ERR] {label[:50]} -> {exc}"
