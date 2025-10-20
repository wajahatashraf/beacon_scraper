import os
import json
import time
import re
from urllib.parse import urlparse, parse_qs
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import importlib
import config

# ================= CONFIG ================= #
PATTERN = re.compile(r"/GetVectorLayer\?QPS=", re.IGNORECASE)


def parse_perf_entry(entry):
    try:
        return json.loads(entry["message"])["message"]
    except Exception:
        return None


def get_qps_token(driver):
    """Captures the QPS token from network logs."""
    try:
        logs = driver.get_log("performance")
    except Exception:
        logs = []

    for entry in logs:
        msg = parse_perf_entry(entry)
        if not msg:
            continue
        if msg.get("method") == "Network.requestWillBeSent":
            url = msg.get("params", {}).get("request", {}).get("url", "")
            if PATTERN.search(url):
                qs = parse_qs(urlparse(url).query)
                qps_token = qs.get("QPS", [""])[0]
                if qps_token:
                    return qps_token
    return None


def open_and_get_qps(driver):
    importlib.reload(config)  # <-- reload config to get updated values
    URL = config.BEACON_URL
    """Open the URL, optionally click 'Agree', and extract QPS token."""
    print(f"\n🌐 Opening: {URL}")
    driver.get(URL)

    try:
        wait = WebDriverWait(driver, 10)
        # Try to find the agree button if it appears
        agree_buttons = driver.find_elements(By.CSS_SELECTOR, "a.btn.btn-primary.button-1")
        if agree_buttons:
            driver.execute_script("arguments[0].click();", agree_buttons[0])
            print("✅ Clicked 'Agree'")
        else:
            print("ℹ️ 'Agree' button not shown, continuing...")
    except Exception as e:
        print(f"⚠️ No 'Agree' button this time: {e}")

    # wait for network to settle
    time.sleep(6)

    qps_token = get_qps_token(driver)
    retry = 0
    while not qps_token and retry < 3:
        print("🔁 Retrying QPS capture...")
        time.sleep(3)
        qps_token = get_qps_token(driver)
        retry += 1

    if not qps_token:
        print("❌ Still no QPS token found after retries.")
    else:
        print(f"✅ Got QPS token: {qps_token[:60]}...")

    return qps_token


def download_batch(driver, qps_token, extents, batch_num,REQUEST_TEMPLATE):
    """Injects JS to fetch and download JSON for multiple extents in parallel."""
    js_code = f"""
    (async function() {{
        const qpsToken = "{qps_token}";
        const extents = {json.dumps(extents)};
        const requestDataTemplate = {json.dumps(REQUEST_TEMPLATE)};
        const apiUrl = `https://beacon.schneidercorp.com/api/beaconCore/GetVectorLayer?QPS=${{qpsToken}}`;

        const delay = ms => new Promise(r => setTimeout(r, ms));

        // Limit concurrency to avoid throttling
        const MAX_PARALLEL = 5;
        let active = 0;
        let index = 0;

        async function fetchExtent(extent) {{
            const requestData = {{ ...requestDataTemplate, ext: extent }};
            try {{
                const response = await fetch(apiUrl, {{
                    method: "POST",
                    headers: {{
                        "Content-Type": "application/json",
                        "Accept": "text/plain, */*; q=0.01"
                    }},
                    body: JSON.stringify(requestData)
                }});
                if (!response.ok) throw new Error("HTTP " + response.status);
                const data = await response.json();

                const fileName = `${{extent.minx}}_${{extent.maxx}}_${{extent.miny}}_${{extent.maxy}}.json`;
                const blob = new Blob([JSON.stringify(data, null, 2)], {{ type: "application/json" }});
                const a = document.createElement("a");
                a.href = URL.createObjectURL(blob);
                a.download = fileName;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                console.log("✅ Downloaded:", fileName);
            }} catch (err) {{
                console.error("❌ Error for extent", extent, err);
            }}
        }}

        async function runBatch() {{
            while (index < extents.length) {{
                if (active < MAX_PARALLEL) {{
                    const extent = extents[index++];
                    active++;
                    fetchExtent(extent).finally(() => active--);
                }}
                await delay(300); // small pacing between requests
            }}
            while (active > 0) {{
                await delay(500);
            }}
            console.log("✅ Batch {batch_num} complete: Downloaded", extents.length, "extents");
        }}

        runBatch();
    }})();"""

    print(f"🚀 Injecting batch #{batch_num} with {len(extents)} extents...")
    driver.execute_script(js_code)


def capture_qps_and_download():
    importlib.reload(config)  # <-- reload config to get updated values
    layer_id = config.layer_id
    layer_name = config.layer_name
    FOLDER_NAME =config.FOLDER_NAME
    print(layer_name,layer_id)

    # Folder for JSON downloads
    DOWNLOAD_FOLDER = os.path.join(os.getcwd(), FOLDER_NAME, layer_name, "json")
    os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

    # Request template must use the current layer_id
    REQUEST_TEMPLATE = {
        "layerId": layer_id,
        "useSelection": False,
        "spatialRelation": 1,
        "featureLimit": 1500,
        "wkt": None
    }

    # Load extents from file
    EXTENT_FILE = os.path.join(os.getcwd(), FOLDER_NAME, "finishnet.json")
    if not os.path.exists(EXTENT_FILE):
        raise FileNotFoundError(f"❌ Could not find extent file: {EXTENT_FILE}")

    with open(EXTENT_FILE, "r") as f:
        EXTENTS = json.load(f)

    batch_size = 250
    total_batches = (len(EXTENTS) + batch_size - 1) // batch_size

    for batch_num in range(total_batches):
        start = batch_num * batch_size
        end = min(start + batch_size, len(EXTENTS))
        batch_extents = EXTENTS[start:end]

        print(f"\n========== 📦 Processing batch {batch_num+1}/{total_batches} "
              f"({len(batch_extents)} extents) ==========")

        # === create fresh driver for each batch ===
        options = uc.ChromeOptions()
        options.add_argument("--start-maximized")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
        options.add_argument("--disable-background-timer-throttling")
        options.add_argument("--disable-backgrounding-occluded-windows")
        options.add_argument("--disable-renderer-backgrounding")
        prefs = {
            "download.default_directory": DOWNLOAD_FOLDER,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
            "profile.default_content_setting_values.automatic_downloads": 1  # ✅ allow multiple automatic downloads
        }
        options.add_experimental_option("prefs", prefs)
        driver = uc.Chrome(options=options)
        driver.execute_cdp_cmd("Network.enable", {})

        qps_token = open_and_get_qps(driver)
        if not qps_token:
            print(f"⚠️ Failed to get QPS token for batch {batch_num+1}, skipping.")
            driver.quit()
            continue

        qps_file = os.path.join(DOWNLOAD_FOLDER, f"qps_batch_{batch_num+1}.txt")
        with open(qps_file, "w") as f:
            f.write(qps_token)

        download_batch(driver, qps_token, batch_extents, batch_num + 1,REQUEST_TEMPLATE)

        # Wait dynamically for downloads to finish
        # === WAIT UNTIL DOWNLOADS STABILIZE ===
        print("⏳ Waiting for downloads to finish...")

        prev_count = 0
        stable_rounds = 0  # how many checks with no new files
        max_stable_rounds = 3  # stop after 3 consecutive checks (≈15s)
        max_wait_time = 120  # absolute upper limit (failsafe)
        start_time = time.time()

        while True:
            files = [f for f in os.listdir(DOWNLOAD_FOLDER) if f.endswith(".json")]
            curr_count = len(files)

            if curr_count == prev_count:
                stable_rounds += 1
            else:
                stable_rounds = 0
                prev_count = curr_count

            # ✅ exit if no new files for ~15 seconds
            if stable_rounds >= max_stable_rounds:
                print(f"✅ Downloads stabilized at {curr_count} files.")
                break

            # ⏱️ safety stop if taking too long
            if time.time() - start_time > max_wait_time:
                print("⚠️ Timeout waiting for downloads — continuing anyway.")
                break

            time.sleep(5)

        print(f"✅ Batch {batch_num+1} done ({curr_count} files total).")
        driver.quit()
        time.sleep(5)

    print("\n✅ All batches processed.")


if __name__ == "__main__":
    capture_qps_and_download()
