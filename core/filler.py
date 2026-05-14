from __future__ import annotations

import random
import time
import unicodedata
from threading import Event
from typing import Callable

from rich.console import Console
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from core.config import RunConfig
from core.driver import create_driver, detect_form_language
from core.handlers import detect_and_fill

console = Console()

_NEXT_TEXTS = {"tiếp", "tiếp theo", "tiếp tục", "next", "continue", "tiep", "tiep theo", "tiep tuc"}
_SUBMIT_TEXTS = {"gửi", "submit", "nộp", "send", "gui"}
_BACK_TEXTS = {"quay lại", "back", "previous", "trước", "quay lai"}


def _norm(text: str) -> str:
    return unicodedata.normalize("NFC", text).lower().strip()


def _get_question_blocks(driver: WebDriver):
    return driver.find_elements(By.CSS_SELECTOR, "div[data-params]")


def _btn_text(button) -> str:
    text = (button.text or "").strip()
    if not text:
        text = (button.get_attribute("aria-label") or button.get_attribute("value") or "").strip()
    if not text:
        for span in button.find_elements(By.TAG_NAME, "span"):
            text = (span.text or "").strip()
            if text:
                break
    return _norm(text)


def _classify_buttons(driver: WebDriver, log_fn: Callable[[str], None]) -> tuple[list, list]:
    next_buttons: list = []
    submit_buttons: list = []

    primary = driver.find_elements(By.CSS_SELECTOR, "[jsname='P2WeLd']")
    for button in primary:
        text = _btn_text(button)
        if not text:
            continue
        if any(keyword in text for keyword in _SUBMIT_TEXTS):
            submit_buttons.append(button)
        elif any(keyword in text for keyword in _NEXT_TEXTS):
            next_buttons.append(button)

    if next_buttons or submit_buttons:
        _log_buttons(next_buttons, submit_buttons, log_fn)
        return next_buttons, submit_buttons

    try:
        candidates = driver.find_elements(
            By.XPATH,
            "//div[@role='button' and not(ancestor::div[@data-params])]"
            " | //button[not(ancestor::div[@data-params])]"
            " | //input[@type='submit']",
        )
    except Exception:
        candidates = driver.find_elements(
            By.CSS_SELECTOR,
            "div[role='button'], button, input[type='submit']",
        )

    for button in candidates:
        text = _btn_text(button)
        if not text:
            continue
        if any(keyword in text for keyword in _BACK_TEXTS):
            continue
        if any(keyword in text for keyword in _SUBMIT_TEXTS):
            submit_buttons.append(button)
        elif any(keyword in text for keyword in _NEXT_TEXTS):
            next_buttons.append(button)

    _log_buttons(next_buttons, submit_buttons, log_fn)
    return next_buttons, submit_buttons


def _log_buttons(next_buttons: list, submit_buttons: list, log_fn: Callable[[str], None]) -> None:
    if next_buttons:
        texts = [_btn_text(button) for button in next_buttons]
        log_fn(f"  [dim]🔍 Nút Next tìm thấy: {texts}[/dim]")
    if submit_buttons:
        texts = [_btn_text(button) for button in submit_buttons]
        log_fn(f"  [dim]🔍 Nút Submit tìm thấy: {texts}[/dim]")


def _safe_click(driver: WebDriver, button) -> bool:
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", button)
        button.click()
        return True
    except Exception:
        try:
            driver.execute_script("arguments[0].click();", button)
            return True
        except Exception:
            return False


def _wait_page_change(driver: WebDriver, anchor, timeout: int = 12) -> None:
    if anchor is None:
        time.sleep(1.5)
        return
    try:
        WebDriverWait(driver, timeout).until(EC.staleness_of(anchor))
    except Exception:
        time.sleep(1.5)
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-params]"))
        )
    except Exception:
        time.sleep(1.0)


def _replace_driver(
    config: RunConfig,
    lang: str,
    driver_ref: list | None,
    old_driver: WebDriver | None = None,
) -> WebDriver:
    if old_driver is not None:
        try:
            old_driver.quit()
        except Exception:
            pass

    new_driver = create_driver(lang=lang)
    if driver_ref is not None:
        driver_ref.clear()
        driver_ref.append(new_driver)
    return new_driver


def fill_form_once(
    driver: WebDriver,
    config: RunConfig,
    submission_idx: int,
    total: int,
    lang: str,
    log_fn: Callable[[str], None],
    stop_event: Event | None = None,
) -> bool:
    log_fn(f"\n[bold cyan]─── Submission {submission_idx}/{total} ───[/bold cyan]")

    if stop_event and stop_event.is_set():
        return False

    try:
        driver.get(config.form_url)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-params]"))
        )
    except Exception as exc:
        log_fn(f"  [red]❌ Không load được form: {exc}[/red]")
        return False

    page_num = 1
    while True:
        if stop_event and stop_event.is_set():
            log_fn("  [yellow]⛔ Đã dừng[/yellow]")
            return False

        log_fn(f"  [dim]📄 Trang {page_num}[/dim]")
        time.sleep(0.3)

        blocks = _get_question_blocks(driver)
        anchor = blocks[0] if blocks else None

        if not blocks:
            log_fn("  [yellow]⚠ Không tìm thấy câu hỏi trên trang này[/yellow]")

        for block in blocks:
            if stop_event and stop_event.is_set():
                return False
            try:
                result = detect_and_fill(block, driver, config)
                log_fn(f"  [green]✓[/green] {result}")
            except Exception as exc:
                log_fn(f"  [red]✗ Lỗi câu hỏi: {exc}[/red]")

        time.sleep(0.3)
        next_buttons, submit_buttons = _classify_buttons(driver, log_fn)

        if next_buttons:
            button = next_buttons[0]
            text = _btn_text(button)
            log_fn(f"  [dim]→ Click '{text}'[/dim]")
            if _safe_click(driver, button):
                _wait_page_change(driver, anchor)
                page_num += 1
                continue
            log_fn("  [red]❌ Không click được nút Next[/red]")
            return False

        if config.no_submit:
            log_fn("  [yellow]⏸ Preview mode — bỏ qua Submit[/yellow]")
            return True

        if submit_buttons:
            button = submit_buttons[0]
            text = _btn_text(button)
            log_fn(f"  [dim]→ Click '{text}'[/dim]")
            if _safe_click(driver, button):
                time.sleep(1.5)
                log_fn("  [bold green]✅ Đã gửi form![/bold green]")
                return True
            log_fn("  [red]❌ Không click được nút Submit[/red]")
            return False

        log_fn("  [red]❌ Không tìm thấy nút Next hoặc Submit[/red]")
        return False


def run_all(
    config: RunConfig,
    log_fn: Callable[[str], None] | None = None,
    stop_event: Event | None = None,
    driver_ref: list | None = None,
    quota_fn: Callable[[], None] | None = None,
    progress_fn: Callable[[int, int, int], None] | None = None,
) -> dict:
    """
    Returns: {"success": N, "fail": N}
    """
    if log_fn is None:
        log_fn = lambda message: console.print(message)

    init_lang = "vi" if config.form_language in ("auto", "vi") else "en"
    driver = _replace_driver(config, init_lang, driver_ref)

    lang = init_lang
    if config.form_language == "auto":
        try:
            driver.get(config.form_url)
            WebDriverWait(driver, 12).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            lang = detect_form_language(driver)
            log_fn(f"  [dim]🌐 Phát hiện ngôn ngữ form: {lang.upper()}[/dim]")
        except Exception:
            lang = "vi"

    success = 0
    fail = 0
    if progress_fn:
        progress_fn(success, fail, config.n_submissions)

    try:
        for submission_idx in range(1, config.n_submissions + 1):
            if stop_event and stop_event.is_set():
                log_fn("\n[yellow]⛔ Đã dừng bởi người dùng[/yellow]")
                break

            ok = False
            last_error: Exception | None = None

            for attempt in range(1, 4):
                if stop_event and stop_event.is_set():
                    break
                try:
                    ok = fill_form_once(
                        driver,
                        config,
                        submission_idx,
                        config.n_submissions,
                        lang,
                        log_fn,
                        stop_event,
                    )
                    if ok:
                        break
                    if attempt < 3:
                        log_fn(f"  [yellow]⚠ Thử lại {attempt}/3 cho submission này[/yellow]")
                        driver = _replace_driver(config, lang, driver_ref, driver)
                except Exception as exc:
                    last_error = exc
                    log_fn(f"  [yellow]⚠ Lỗi lần {attempt}/3: {exc}[/yellow]")
                    if attempt < 3:
                        driver = _replace_driver(config, lang, driver_ref, driver)

            if last_error is not None and not ok:
                log_fn(f"  [red]❌ Bỏ qua submission do lỗi: {last_error}[/red]")

            if ok:
                success += 1
                if quota_fn and not config.no_submit:
                    quota_fn()
            else:
                fail += 1

            if progress_fn:
                progress_fn(success, fail, config.n_submissions)

            if stop_event and stop_event.is_set():
                continue

            if submission_idx < config.n_submissions:
                delay = random.uniform(config.delay_min, config.delay_max)
                log_fn(f"\n  [dim]⏳ Chờ {delay:.1f}s...[/dim]")
                for _ in range(max(1, int(delay * 10))):
                    if stop_event and stop_event.is_set():
                        break
                    time.sleep(0.1)
                if delay == 0:
                    time.sleep(0.01)

    except KeyboardInterrupt:
        log_fn("\n[yellow]⛔ Đã dừng bởi người dùng (Ctrl+C)[/yellow]")
    finally:
        try:
            driver.quit()
        except Exception:
            pass

        separator = "═" * 45
        log_fn(f"\n[bold]{separator}[/bold]")
        log_fn("  [bold]📊 KẾT QUẢ:[/bold]")
        log_fn(f"     ✅ Thành công : [green]{success}[/green]/{config.n_submissions}")
        log_fn(f"     ❌ Thất bại   : [red]{fail}[/red]/{config.n_submissions}")
        log_fn(f"[bold]{separator}[/bold]")

    return {"success": success, "fail": fail}
