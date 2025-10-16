# capture_getvectorlayer_qps.py
import json
import time
import re
from urllib.parse import urlparse, parse_qs
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

URL = "https://beacon.schneidercorp.com/Application.aspx?AppID=55&LayerID=375&PageTypeID=1&PageID=916"
PATTERN = re.compile(r"/GetVectorLayer\?QPS=", re.IGNORECASE)  # match GetVectorLayer calls


def enable_perf_and_network(options):
    """Enable Chrome DevTools Protocol performance/network logging"""
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    return options


def parse_perf_entry(entry):
    """Decode Chrome performance log entries"""
    try:
        return json.loads(entry["message"])["message"]
    except Exception:
        return None


def capture_qps_value():
    opts = Options()
    opts.add_argument("--start-maximized")
    opts.add_experimental_option("detach", True)
    opts = enable_perf_and_network(opts)

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)

    # Enable CDP network logging
    try:
        driver.execute_cdp_cmd("Network.enable", {})
    except Exception as e:
        print("⚠️ Could not call Network.enable:", e)

    driver.get(URL)

    # Click "Agree"
    try:
        wait = WebDriverWait(driver, 20)
        agree = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a.btn.btn-primary.button-1")))
        agree.click()
        print("✅ Clicked 'Agree'")
    except Exception as e:
        print("⚠️ Couldn't click Agree:", e)

    # Wait for network activity
    time.sleep(8)

    logs = driver.get_log("performance")
    qps_value = None

    for entry in logs:
        msg = parse_perf_entry(entry)
        if not msg:
            continue

        if msg.get("method") == "Network.requestWillBeSent":
            url = msg.get("params", {}).get("request", {}).get("url", "")
            if PATTERN.search(url):
                qs = parse_qs(urlparse(url).query)
                qps_value = qs.get("QPS", [""])[0]
                if qps_value:
                    print("\n✅ Found QPS value:\n")
                    print(qps_value)
                    break  # stop after first match

    if not qps_value:
        print("❌ No /GetVectorLayer?QPS= request found.")

    # Optionally save to file
    if qps_value:
        with open("qps_value.txt", "w", encoding="utf-8") as f:
            f.write(qps_value)
        print("\n💾 Saved QPS value to qps_value.txt")

    input("Press Enter to close browser...")
    driver.quit()


if __name__ == "__main__":
    capture_qps_value()
