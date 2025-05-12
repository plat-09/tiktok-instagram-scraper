from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    page.goto("https://vm.tiktok.com/ZMBKSPtKr/", timeout=60000)
    input("Нажми Enter, чтобы закрыть браузер...")
    browser.close()