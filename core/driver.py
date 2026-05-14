# from __future__ import annotations

# from selenium import webdriver
# from selenium.webdriver.chrome.options import Options
# from selenium.webdriver.chrome.service import Service
# from selenium.webdriver.remote.webdriver import WebDriver
# from webdriver_manager.chrome import ChromeDriverManager


# def create_driver(headless: bool = False, lang: str = "vi") -> WebDriver:
#     """Tạo Chrome WebDriver với các tùy chọn chống phát hiện bot."""
#     options = Options()

#     locale = "vi-VN" if lang == "vi" else "en-US"
#     options.add_argument(f"--lang={locale}")

#     if headless:
#         options.add_argument("--headless=new")
#         options.add_argument("--window-size=1366,768")

#     options.add_argument("--no-sandbox")
#     options.add_argument("--disable-dev-shm-usage")
#     options.add_argument("--disable-gpu")
#     options.add_argument("--disable-software-rasterizer")
#     options.add_argument("--disable-extensions")
#     options.add_argument("--single-process")
#     options.add_argument("--disable-blink-features=AutomationControlled")
#     options.add_experimental_option("excludeSwitches", ["enable-automation"])
#     options.add_experimental_option("useAutomationExtension", False)
#     options.add_argument(
#         "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
#         "AppleWebKit/537.36 (KHTML, like Gecko) "
#         "Chrome/124.0.0.0 Safari/537.36"
#     )

#     service = Service(ChromeDriverManager().install())
#     driver = webdriver.Chrome(service=service, options=options)

#     # Xóa thuộc tính navigator.webdriver để tránh phát hiện Selenium
#     driver.execute_cdp_cmd(
#         "Page.addScriptToEvaluateOnNewDocument",
#         {"source": "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"},
#     )
#     return driver


# def detect_form_language(driver: WebDriver) -> str:
#     """
#     Phát hiện ngôn ngữ form đang mở bằng cách tìm text của nút điều hướng.
#     Trả về 'vi' hoặc 'en'.
#     """
#     try:
#         page_source = driver.page_source.lower()
#         # Dấu hiệu tiếng Việt
#         vi_markers = ["tiếp theo", "tiếp tục", "gửi", "submit form", "tiếp"]
#         for marker in vi_markers:
#             if marker in page_source:
#                 return "vi"
#         # Mặc định tiếng Anh nếu không tìm thấy dấu hiệu Việt
#         return "en"
#     except Exception:
#         return "vi"

from __future__ import annotations

import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.remote.webdriver import WebDriver

# Tự động detect Docker/CI environment
_IN_DOCKER = os.path.exists("/.dockerenv") or os.environ.get("RUNNING_IN_DOCKER") == "1"


def create_driver(lang: str = "vi") -> WebDriver:
    options = Options()

    locale = "vi-VN" if lang == "vi" else "en-US"
    options.add_argument(f"--lang={locale}")

    if _IN_DOCKER:
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1366,768")

    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )

    driver = webdriver.Chrome(options=options)
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"},
    )
    return driver

def detect_form_language(driver: WebDriver) -> str:
    try:
        page_source = driver.page_source.lower()
        vi_markers = ["tiếp theo", "tiếp tục", "gửi", "submit form", "tiếp"]
        for marker in vi_markers:
            if marker in page_source:
                return "vi"
        return "en"
    except Exception:
        return "vi"