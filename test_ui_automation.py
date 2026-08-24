"""
Automated UI & Integration Test Suite for Scribd Downloader Web App
===================================================================
Uses Selenium WebDriver to automatically test page loading, URL validation,
DOM elements, advanced drawer toggles, and API endpoints.
"""

import sys
import threading
import time
import requests
import uvicorn
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Force UTF-8 stdout encoding for Windows console compatibility
sys.stdout.reconfigure(encoding='utf-8')

TEST_PORT = 8089
BASE_URL = f"http://127.0.0.1:{TEST_PORT}"


def run_server():
    uvicorn.run("app:app", host="127.0.0.1", port=TEST_PORT, log_level="warning")


def main():
    print("==================================================")
    print(" Running Automated UI Tests with Selenium")
    print("==================================================")

    # Start server in background thread
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Wait for server to become responsive
    for _ in range(20):
        try:
            r = requests.get(f"{BASE_URL}/api/downloads")
            if r.status_code == 200:
                print("[OK] FastAPI Server online")
                break
        except Exception:
            time.sleep(0.3)

    # Set up headless Chrome
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=options)
    try:
        # 1. Open Web UI
        driver.get(BASE_URL)
        print("[OK] Page loaded successfully")

        # 2. Check title
        assert "Scribd Downloader" in driver.title
        print(f"[OK] Title verified: '{driver.title}'")

        # 3. Verify Header and Status Badge
        badge = driver.find_element(By.ID, "server-status")
        assert "Server Ready" in badge.text
        print("[OK] Server status badge verified")

        # 4. Test URL input and validation
        url_input = driver.find_element(By.ID, "scribd-url")
        url_input.clear()
        url_input.send_keys("https://www.scribd.com/document/903361807/WorkdaySimpleIntegrations-EIB-31v2")

        # Wait for validation message
        val_msg = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".url-validation-msg.valid"))
        )
        assert "Valid Scribd Document Link" in val_msg.text
        print("[OK] Live URL validation success verified")

        # 5. Verify Embed preview box appeared
        preview_box = driver.find_element(By.ID, "embed-preview-box")
        assert "hidden" not in preview_box.get_attribute("class")
        print("[OK] Embed preview box displayed")

        # 6. Test Advanced Settings Drawer Toggle
        toggle_btn = driver.find_element(By.CSS_SELECTOR, ".btn-text")
        drawer = driver.find_element(By.ID, "settings-drawer")
        assert "hidden" in drawer.get_attribute("class")
        
        toggle_btn.click()
        time.sleep(0.3)
        assert "hidden" not in drawer.get_attribute("class")
        print("[OK] Advanced settings drawer expanded successfully")

        toggle_btn.click()
        time.sleep(0.3)
        assert "hidden" in drawer.get_attribute("class")
        print("[OK] Advanced settings drawer collapsed successfully")

        # 7. Check History List Container
        history_list = driver.find_element(By.ID, "history-list")
        assert history_list is not None
        print("[OK] Downloads History list container verified")

        print("\n==================================================")
        print(" ALL AUTOMATED UI TESTS PASSED SUCCESSFULLY!")
        print("==================================================")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
