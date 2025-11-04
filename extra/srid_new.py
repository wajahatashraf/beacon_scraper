# srid_new.py
import re
import time
import random
import os
import json
from typing import Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc

URL = "https://beacon.schneidercorp.com/Application.aspx?AppID=55&LayerID=375&PageTypeID=1&PageID=916"
FOLDER_NAME = "output"
print(f'folder path: {FOLDER_NAME}')
def make_options(headless: bool):
    opts = uc.ChromeOptions()
    user_agent = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    opts.add_argument(f"--user-agent={user_agent}")
    opts.add_argument("--lang=en-US,en")
    opts.add_argument("--start-maximized")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--disable-infobars")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--use-fake-ui-for-media-stream")
    opts.add_argument("--allow-file-access-from-files")
    opts.add_argument("--autoplay-policy=no-user-gesture-required")
    opts.add_argument("--enable-experimental-web-platform-features")
    if headless:
        opts.add_argument("--headless=new")
    prefs = {"profile.managed_default_content_settings.images": 2}  # disable images
    opts.add_experimental_option("prefs", prefs)
    return opts


def extract_srid_and_layers(headless: bool = False):
    options = make_options(headless)
    driver = None
    start_time = time.time()
    srid = None
    try:
        print("🚀 Launching Chrome...")
        driver = uc.Chrome(options=options)

        print(f"🌐 Opening URL: {URL}")
        driver.get(URL)

        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        time.sleep(0.5 + random.random() * 0.5)

        print("🔍 Extracting SRID...")
        page_source = driver.page_source

        srid_match = re.search(r'"Projections":\s*\[\s*\{[^}]*?"SRID"\s*:\s*(\d+)', page_source)
        if srid_match:
            srid = srid_match.group(1)
            print("✅ SRID found in Projections block")
        else:
            fallback = re.search(r"EPSG[:\s\"']*(\d{4,6})", page_source, re.IGNORECASE)
            if fallback:
                srid = fallback.group(1)
                print("✅ SRID found in fallback search")
            else:
                print("⚠️ SRID not found")

        print("🧩 Extracting Zoning Layers...")
        pattern = re.compile(r'{"LayerId":(\d+).*?"LayerName":"(.*?)"', re.DOTALL)
        matches = pattern.findall(page_source)
        zoning_layers = [
            {"LayerId": int(layer_id), "LayerName": re.sub(r'[^a-zA-Z0-9_ ]', '', name.replace("/", " ")).strip()}
            for layer_id, name in matches
            if "zoning" in name.lower()
        ]

        if zoning_layers:
            print("✅ Found zoning layers:")
            for layer in zoning_layers:
                print(f"   🗂️ {layer['LayerName']} (LayerId: {layer['LayerId']})")
            os.makedirs(FOLDER_NAME, exist_ok=True)
            layers_path = os.path.join(FOLDER_NAME, "zoning_layers.json")
            with open(layers_path, "w", encoding="utf-8") as f:
                json.dump(zoning_layers, f, indent=2)
            print(f"💾 Saved zoning layer info to: {layers_path}")
        else:
            print("⚠️ No zoning layers found.")

    except Exception as e:
        print("❌ Error occurred:", e)

    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
        end_time = time.time()
        print(f"⏱ Response time: {end_time - start_time:.2f} seconds")

    return srid, zoning_layers


if __name__ == "__main__":
    srid_value, zoning_layers = extract_srid_and_layers(headless=True)
    if srid_value:
        print("🎯 Done — SRID:", srid_value)
    else:
        print("🎯 Done — SRID not found.")
