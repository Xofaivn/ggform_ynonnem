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

_NEXT_TEXTS   = {"tiếp", "tiếp theo", "tiếp tục", "next", "continue", "tiep", "tiep theo", "tiep tuc"}
_SUBMIT_TEXTS = {"gửi", "submit", "nộp", "send", "gui"}
_BACK_TEXTS   = {"quay lại", "back", "previous", "trước", "quay lai"}


def _norm(s: str) -> str:
    return unicodedata.normalize("NFC", s).lower().strip()


def _get_question_blocks(driver: WebDriver):
    return driver.find_elements(By.CSS_SELECTOR, "div[data-params]")


def _btn_text(btn) -> str:
    t = (btn.text or "").strip()
    if not t:
        t = (btn.get_attribute("aria-label") or btn.get_attribute("value") or "").strip()
    if not t:
        for span in btn.find_elements(By.TAG_NAME, "span"):
            t = (span.text or "").strip()
            if t:
                break
    return _norm(t)


def _classify_buttons(driver: WebDriver, log_fn: Callable) -> tuple[list, list]:
    next_btns: list = []
    submit_btns: list = []

    primary = driver.find_elements(By.CSS_SELECTOR, "[jsname='P2WeLd']")
    for btn in primary:
        t = _btn_text(btn)
        if not t:
            continue
        if any(s in t for s in _SUBMIT_TEXTS):
            submit_btns.append(btn)
        elif any(s in t for s in _NEXT_TEXTS):
            next_btns.append(btn)

    if next_btns or submit_btns:
        _log_buttons(next_btns, submit_btns, log_fn)
        return next_btns, submit_btns

    try:
        candidates = driver.find_elements(
            By.XPATH,
            "//div[@role='button' and not(ancestor::div[@data-params])]"
            " | //button[not(ancestor::div[@data-params])]"
            " | //input[@type='submit']"
        )
    except Exception:
        candidates = driver.find_elements(
            By.CSS_SELECTOR, "div[role='button'], button, input[type='submit']"
        )

    for btn in candidates:
        t = _btn_text(btn)
        if not t:
            continue
        if any(s in t for s in _BACK_TEXTS):
            continue
        if any(s in t for s in _SUBMIT_TEXTS):
            submit_btns.append(btn)
        elif any(s in t for s in _NEXT_TEXTS):
            next_btns.append(btn)

    _log_buttons(next_btns, submit_btns, log_fn)
    return next_btns, submit_btns


def _log_buttons(next_btns: list, submit_btns: list, log_fn: Callable) -> None:
    if next_btns:
        texts = [_btn_text(b) for b in next_btns]
        log_fn(f"  [dim]🔍 Nút Next tìm thấy: {texts}[/dim]")
    if submit_btns:
        texts = [_btn_text(b) for b in submit_btns]
        log_fn(f"  [dim]🔍 Nút Submit tìm thấy: {texts}[/dim]")


def _safe_click(driver: WebDriver, btn) -> bool:
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
        btn.click()
        return True
    except Exception:
        try:
            driver.execute_script("arguments[0].click();", btn)
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


def fill_form_once(
    driver: WebDriver,
    config: RunConfig,
    submission_idx: int,
    total: int,
    lang: str,
    log_fn: Callable,
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
    except Exception as e:
        log_fn(f"  [red]❌ Không load được form: {e}[/red]")
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
            except Exception as e:
                log_fn(f"  [red]✗ Lỗi câu hỏi: {e}[/red]")

        time.sleep(0.3)

        next_btns, submit_btns = _classify_buttons(driver, log_fn)

        if next_btns:
            btn = next_btns[0]
            t = _btn_text(btn)
            log_fn(f"  [dim]→ Click '{t}'[/dim]")
            if _safe_click(driver, btn):
                _wait_page_change(driver, anchor)
                page_num += 1
                continue
            else:
                log_fn("  [red]❌ Không click được nút Next[/red]")
                return False

        if config.no_submit:
            log_fn("  [yellow]⏸ Preview mode — bỏ qua Submit[/yellow]")
            return True

        if submit_btns:
            btn = submit_btns[0]
            t = _btn_text(btn)
            log_fn(f"  [dim]→ Click '{t}'[/dim]")
            if _safe_click(driver, btn):
                time.sleep(1.5)
                log_fn("  [bold green]✅ Đã gửi form![/bold green]")
                return True
            else:
                log_fn("  [red]❌ Không click được nút Submit[/red]")
                return False

        log_fn("  [red]❌ Không tìm thấy nút Next hoặc Submit[/red]")
        return False


def run_all(
    config: RunConfig,
    log_fn: Callable | None = None,
    stop_event: Event | None = None,
    driver_ref: list | None = None,
) -> dict:
    """
    log_fn(msg: str) — nhận log có Rich markup.
    stop_event — set() từ ngoài để dừng sớm.
    driver_ref — list 1 phần tử, ghi driver vào để caller có thể quit.
    Returns: {"success": N, "fail": N}
    """
    if log_fn is None:
        log_fn = lambda msg: console.print(msg)

    init_lang = "vi" if config.form_language in ("auto", "vi") else "en"
    driver = create_driver(headless=config.headless, lang=init_lang)
    if driver_ref is not None:
        driver_ref.clear()
        driver_ref.append(driver)

    lang = init_lang
    if config.form_language == "auto":
        try:
            driver.get(config.form_url)
            WebDriverWait(driver, 12).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            lang = detect_form_language(driver)
            log_fn(f"  [dim]🌐 Phát hiện ngôn ngữ form: {lang.upper()}[/dim]")
        except Exception:
            lang = "vi"

    success = 0
    fail = 0

    try:
        for i in range(1, config.n_submissions + 1):
            if stop_event and stop_event.is_set():
                log_fn("\n[yellow]⛔ Đã dừng bởi người dùng[/yellow]")
                break

            ok = fill_form_once(driver, config, i, config.n_submissions, lang, log_fn, stop_event)
            if ok:
                success += 1
            else:
                fail += 1

            if i < config.n_submissions and not (stop_event and stop_event.is_set()):
                delay = random.uniform(config.delay_min, config.delay_max)
                log_fn(f"\n  [dim]⏳ Chờ {delay:.1f}s...[/dim]")
                # Sleep interruptible
                for _ in range(int(delay * 10)):
                    if stop_event and stop_event.is_set():
                        break
                    time.sleep(0.1)

    except KeyboardInterrupt:
        log_fn("\n[yellow]⛔ Đã dừng bởi người dùng (Ctrl+C)[/yellow]")

    finally:
        try:
            driver.quit()
        except Exception:
            pass
        sep = "═" * 45
        log_fn(f"\n[bold]{sep}[/bold]")
        log_fn(f"  [bold]📊 KẾT QUẢ:[/bold]")
        log_fn(f"     ✅ Thành công : [green]{success}[/green]/{config.n_submissions}")
        log_fn(f"     ❌ Thất bại   : [red]{fail}[/red]/{config.n_submissions}")
        log_fn(f"[bold]{sep}[/bold]")

    return {"success": success, "fail": fail}
