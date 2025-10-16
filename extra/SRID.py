# extract_srid_from_beacon.py
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import re
import time

URL = "https://beacon.schneidercorp.com/Application.aspx?AppID=55&LayerID=375&PageTypeID=1&PageID=916"

def extract_srid():
    opts = Options()
    opts.add_argument("--start-maximized")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)

    driver.get(URL)

    try:
        # Click "Agree" button if it appears
        wait = WebDriverWait(driver, 15)
        agree_button = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "a.btn.btn-primary.button-1"))
        )
        agree_button.click()
        print("✅ Clicked 'Agree' button.")
    except Exception:
        print("⚠️ 'Agree' button not found or already accepted.")

    # Wait for page content to load
    time.sleep(5)

    # Get page source
    page_source = driver.page_source

    # Extract SRID using regex
    srid_match = re.search(r'"Projections":\[\{.*?"SRID":(\d+)', page_source)
    if srid_match:
        srid = srid_match.group(1)
        print(f"✅ Found SRID: {srid}")
        with open("srid_value.txt", "w") as f:
            f.write(srid)
        print("💾 Saved SRID to srid_value.txt")
    else:
        print("❌ SRID not found in page source.")

    driver.quit()


if __name__ == "__main__":
    extract_srid()
