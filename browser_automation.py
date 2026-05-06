"""Browser automation for Feishu setup."""
import time
from playwright.sync_api import sync_playwright

def main():
    with sync_playwright() as p:
        # Use user's installed Chrome
        browser = p.chromium.launch(
            channel="chrome",
            headless=False,
            args=["--start-maximized"]
        )
        context = browser.new_context viewport=None)
        page = context.new_page()
        
        # Navigate to Feishu app page
        page.goto("https://open.feishu.cn/app")
        page.wait_for_load_state("networkidle")
        
        # Take screenshot
        page.screenshot(path="D:/project/hotclaw/feishu_screenshot.png")
        print("Screenshot saved to D:/project/hotclaw/feishu_screenshot.png")
        
        # Keep browser open for user to see
        input("Press Enter to close browser...")
        browser.close()

if __name__ == "__main__":
    main()