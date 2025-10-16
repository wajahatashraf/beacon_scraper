# extract_layer_info_from_beacon.py
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import re
import json
import time

URL = "https://beacon.schneidercorp.com/Application.aspx?AppID=97&LayerID=963&PageTypeID=1&PageID=959"

def extract_zoning_layer():
    opts = Options()
    opts.add_argument("--start-maximized")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)

    driver.get(URL)

    # Step 1: Click "Agree" button if it appears
    try:
        wait = WebDriverWait(driver, 15)
        agree_button = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "a.btn.btn-primary.button-1"))
        )
        agree_button.click()
        print("✅ Clicked 'Agree' button.")
    except Exception:
        print("⚠️ 'Agree' button not found or already accepted.")

    # Step 2: Wait for page to load
    time.sleep(5)
    page_source = driver.page_source

    # Step 3: Extract all LayerId and LayerName pairs
    pattern = re.compile(r'{"LayerId":(\d+).*?"LayerName":"(.*?)"', re.DOTALL)
    matches = pattern.findall(page_source)

    if not matches:
        print("❌ No LayerId/LayerName pairs found in page source.")
        driver.quit()
        return

    zoning_layers = [
        {"LayerId": layer_id, "LayerName": name}
        for layer_id, name in matches
        if "zoning" in name.lower()
    ]

    if not zoning_layers:
        print("⚠️ No layer found containing 'zoning'.")
    else:
        print("✅ Found the following zoning-related layers:")
        for layer in zoning_layers:
            print(f"   🗂️ {layer['LayerName']} (LayerId: {layer['LayerId']})")

        with open("zoning_layers.json", "w", encoding="utf-8") as f:
            json.dump(zoning_layers, f, indent=2)
        print("💾 Saved zoning layer info to zoning_layers.json")

    driver.quit()


if __name__ == "__main__":
    extract_zoning_layer()
