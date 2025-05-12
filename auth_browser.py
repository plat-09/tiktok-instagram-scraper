from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)  # Открыть с интерфейсом
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://www.instagram.com/")
    print("🔑 Войди в Instagram, а потом нажми Enter в терминале...")
    input()
    context.storage_state(path="auth.json")  # сохраняем cookies и токены
    print("✅ Cookies сохранены в auth.json")
    browser.close()