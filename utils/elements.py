from __future__ import annotations

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

# Danh sách keyword nhận diện "Other / Mục khác" — áp dụng cho mọi loại câu hỏi
_OTHER_KEYWORDS = {
    "mục khác", "khác", "other", "other:", "mục khác:", "__other_option__",
    "không muốn chia sẻ",
}


def get_option_text(element: WebElement) -> str:
    """Lấy text hiển thị của 1 option trong Google Forms (thử 4 cách)."""
    # 1. Selenium .text
    t = (element.text or "").strip()
    if t:
        return t
    # 2. aria-label
    t = (element.get_attribute("aria-label") or "").strip()
    if t:
        return t
    # 3. data-value
    t = (element.get_attribute("data-value") or "").strip()
    if t:
        return t
    # 4. Nested spans
    for span in element.find_elements(By.TAG_NAME, "span"):
        t = (span.text or "").strip()
        if t:
            return t
    return ""


def is_other_option(element: WebElement) -> bool:
    """Trả về True nếu option này là 'Mục khác / Other' → không bao giờ chọn."""
    text = get_option_text(element).lower().strip()
    if not text:
        return False
    # Exact match hoặc startswith cho "other:"
    if text in _OTHER_KEYWORDS:
        return True
    for kw in _OTHER_KEYWORDS:
        if text.startswith(kw):
            return True
    return False


def scroll_and_click(block: WebElement, element: WebElement, driver: WebDriver) -> None:
    """Scroll element vào view rồi click, fallback JS nếu bị chặn."""
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", element)
        element.click()
    except Exception:
        try:
            driver.execute_script("arguments[0].click();", element)
        except Exception:
            pass
