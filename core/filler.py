from __future__ import annotations

import random
import time
import unicodedata

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
    """NFC normalize + lowercase + strip — chuẩn hóa text trước khi so sánh."""
    return unicodedata.normalize("NFC", s).lower().strip()


def _get_question_blocks(driver: WebDriver):
    return driver.find_elements(By.CSS_SELECTOR, "div[data-params]")


def _btn_text(btn) -> str:
    """Lấy text của button, NFC-normalize để so sánh đúng tiếng Việt."""
    t = (btn.text or "").strip()
    if not t:
        t = (btn.get_attribute("aria-label") or btn.get_attribute("value") or "").strip()
    if not t:
        for span in btn.find_elements(By.TAG_NAME, "span"):
            t = (span.text or "").strip()
            if t:
                break
    return _norm(t)


def _classify_buttons(driver: WebDriver) -> tuple[list, list]:
    """
    Phân loại nút navigation: (next_buttons, submit_buttons).
    Ưu tiên tìm trong container navigation của Google Forms,
    sau đó fallback sang text-match toàn trang nhưng loại trừ buttons trong question blocks.
    """
    next_btns: list = []
    submit_btns: list = []

    # 1. Tìm theo jsname của Google Forms (primary action button)
    #    jsname='P2WeLd' = nút Next hoặc Submit (tùy trang)
    #    jsname='dRIPTd' = nút Back
    primary = driver.find_elements(By.CSS_SELECTOR, "[jsname='P2WeLd']")
    for btn in primary:
        t = _btn_text(btn)
        if not t:
            continue
        if any(s in t for s in _SUBMIT_TEXTS):
            submit_btns.append(btn)
        elif any(s in t for s in _NEXT_TEXTS):
            next_btns.append(btn)
        else:
            # jsname P2WeLd nhưng text không khớp → vẫn là primary action
            # nếu chưa có gì khác → đánh dấu tạm thời
            pass

    if next_btns or submit_btns:
        _log_buttons(next_btns, submit_btns)
        return next_btns, submit_btns

    # 2. Fallback: tìm tất cả role=button NGOÀI question blocks
    #    Dùng XPath để loại trừ buttons bên trong div[data-params]
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

    _log_buttons(next_btns, submit_btns)
    return next_btns, submit_btns


def _log_buttons(next_btns: list, submit_btns: list) -> None:
    if next_btns:
        texts = [_btn_text(b) for b in next_btns]
        console.print(f"  [dim]🔍 Nút Next tìm thấy: {texts}[/dim]")
    if submit_btns:
        texts = [_btn_text(b) for b in submit_btns]
        console.print(f"  [dim]🔍 Nút Submit tìm thấy: {texts}[/dim]")


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
    """
    Chờ trang chuyển bằng cách detect element cũ bị stale (biến mất khỏi DOM),
    rồi chờ câu hỏi mới xuất hiện.
    Đây là cách đáng tin cậy hơn so với check find_elements (trả về element cũ ngay).
    """
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


def fill_form_once(driver: WebDriver, config: RunConfig, submission_idx: int, total: int, lang: str) -> bool:
    console.print(f"\n[bold cyan]─── Submission {submission_idx}/{total} ───[/bold cyan]")

    try:
        driver.get(config.form_url)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-params]"))
        )
    except Exception as e:
        console.print(f"  [red]❌ Không load được form: {e}[/red]")
        return False

    page_num = 1
    while True:
        console.print(f"  [dim]📄 Trang {page_num}[/dim]")
        time.sleep(0.3)

        blocks = _get_question_blocks(driver)
        anchor = blocks[0] if blocks else None  # dùng để detect page transition

        if not blocks:
            console.print("  [yellow]⚠ Không tìm thấy câu hỏi trên trang này[/yellow]")

        for block in blocks:
            try:
                result = detect_and_fill(block, driver, config)
                console.print(f"  [green]✓[/green] {result}")
            except Exception as e:
                console.print(f"  [red]✗ Lỗi câu hỏi: {e}[/red]")

        time.sleep(0.3)

        # Phân loại nút hiện trên trang
        next_btns, submit_btns = _classify_buttons(driver)

        # Ưu tiên: nếu có nút Next → click và chờ trang mới
        if next_btns:
            btn = next_btns[0]
            t = _btn_text(btn)
            console.print(f"  [dim]→ Click '{t}'[/dim]")
            if _safe_click(driver, btn):
                _wait_page_change(driver, anchor)
                page_num += 1
                continue
            else:
                console.print("  [red]❌ Không click được nút Next[/red]")
                return False

        # Không có Next → tìm Submit
        if config.no_submit:
            console.print("  [yellow]⏸ Preview mode — bỏ qua Submit[/yellow]")
            return True

        if submit_btns:
            btn = submit_btns[0]
            t = _btn_text(btn)
            console.print(f"  [dim]→ Click '{t}'[/dim]")
            if _safe_click(driver, btn):
                time.sleep(1.5)
                console.print("  [bold green]✅ Đã gửi form![/bold green]")
                return True
            else:
                console.print("  [red]❌ Không click được nút Submit[/red]")
                return False

        console.print("  [red]❌ Không tìm thấy nút Next hoặc Submit[/red]")
        return False


def run_all(config: RunConfig) -> None:
    init_lang = "vi" if config.form_language in ("auto", "vi") else "en"
    driver = create_driver(headless=config.headless, lang=init_lang)

    lang = init_lang
    if config.form_language == "auto":
        try:
            driver.get(config.form_url)
            WebDriverWait(driver, 12).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            lang = detect_form_language(driver)
            console.print(f"  [dim]🌐 Phát hiện ngôn ngữ form: {lang.upper()}[/dim]")
        except Exception:
            lang = "vi"

    success = 0
    fail = 0

    try:
        for i in range(1, config.n_submissions + 1):
            ok = fill_form_once(driver, config, i, config.n_submissions, lang)
            if ok:
                success += 1
            else:
                fail += 1

            if i < config.n_submissions:
                delay = random.uniform(config.delay_min, config.delay_max)
                console.print(f"\n  [dim]⏳ Chờ {delay:.1f}s...[/dim]")
                time.sleep(delay)

    except KeyboardInterrupt:
        console.print("\n[yellow]⛔ Đã dừng bởi người dùng (Ctrl+C)[/yellow]")

    finally:
        driver.quit()
        console.print(f"\n[bold]{'═'*45}[/bold]")
        console.print(f"  [bold]📊 KẾT QUẢ:[/bold]")
        console.print(f"     ✅ Thành công : [green]{success}[/green]/{config.n_submissions}")
        console.print(f"     ❌ Thất bại   : [red]{fail}[/red]/{config.n_submissions}")
        console.print(f"[bold]{'═'*45}[/bold]")
