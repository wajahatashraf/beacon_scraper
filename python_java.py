import os
import json
import time
import re
from urllib.parse import urlparse, parse_qs
import importlib
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import config

# ================= CONFIG ================= #
PATTERN = re.compile(r"/GetVectorLayer\?QPS=", re.IGNORECASE)


def make_options(download_folder, headless=False):
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
    opts.add_argument("--disable-background-timer-throttling")
    opts.add_argument("--disable-backgrounding-occluded-windows")
    opts.add_argument("--disable-renderer-backgrounding")
    # opts.add_argument("--headless=new")
    prefs = {
        "download.default_directory": download_folder,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
        "profile.default_content_setting_values.automatic_downloads": 1,
        "profile.managed_default_content_settings.images": 2,  # disable images
    }
    opts.add_experimental_option("prefs", prefs)
    opts.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    return opts


def parse_perf_entry(entry):
    try:
        return json.loads(entry["message"])["message"]
    except Exception:
        return None


def get_qps_token(driver):
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


def open_and_get_qps(driver, timeout=30):
    """Open the URL, wait until fully loaded, optionally click 'Agree', and extract QPS token."""
    importlib.reload(config)
    URL = config.BEACON_URL
    print(f"\n🌐 Opening: {URL}")
    driver.get(URL)

    try:
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        print("✅ Page fully loaded.")
    except Exception as e:
        print(f"⚠️ Timeout waiting for page load: {e}")

    try:
        agree_buttons = driver.find_elements(By.CSS_SELECTOR, "a.btn.btn-primary.button-1")
        if agree_buttons:
            driver.execute_script("arguments[0].click();", agree_buttons[0])
            print("✅ Clicked 'Agree'")
            time.sleep(3)
        else:
            print("ℹ️ 'Agree' button not shown, continuing...")
    except Exception as e:
        print(f"⚠️ No 'Agree' button this time: {e}")

    qps_token = None
    retry = 0
    max_retry = 10
    while not qps_token and retry < max_retry:
        qps_token = get_qps_token(driver)
        if not qps_token:
            time.sleep(2)
            retry += 1
            print(f"🔁 Waiting for QPS token... attempt {retry}/{max_retry}")

    if not qps_token:
        print("❌ Still no QPS token found after retries.")
    else:
        print(f"✅ Got QPS token: {qps_token[:60]}...")

    return qps_token


def download_batch(driver, qps_token, extents, batch_num, REQUEST_TEMPLATE):
    """Inject JS to fetch and download JSON for multiple extents in parallel."""
    js_code = f"""
    (async function() {{
        const qpsToken = "{qps_token}";
        const extents = {json.dumps(extents)};
        const requestDataTemplate = {json.dumps(REQUEST_TEMPLATE)};
        const apiUrl = `https://beacon.schneidercorp.com/api/beaconCore/GetVectorLayer?QPS=${{qpsToken}}`;
        const delay = ms => new Promise(r => setTimeout(r, ms));
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
                await delay(300);
            }}
            while (active > 0) await delay(500);
            console.log("✅ Batch {batch_num} complete: Downloaded", extents.length, "extents");
        }}
        runBatch();
    }})();
    """
    print(f"🚀 Injecting batch #{batch_num} with {len(extents)} extents...")
    driver.execute_script(js_code)


def capture_qps_and_download():
    importlib.reload(config)
    layer_id = config.layer_id
    layer_name = config.layer_name
    FOLDER_NAME = config.FOLDER_NAME
    print(layer_name, layer_id)

    DOWNLOAD_FOLDER = os.path.join(os.getcwd(), FOLDER_NAME, layer_name, "json")
    os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

    REQUEST_TEMPLATE = {
        "layerId": layer_id,
        "useSelection": False,
        "spatialRelation": 1,
        "featureLimit": 1500,
        "wkt": None
    }

    EXTENT_FILE = os.path.join(os.getcwd(), FOLDER_NAME, "finishnet.json")
    if not os.path.exists(EXTENT_FILE):
        raise FileNotFoundError(f"❌ Could not find extent file: {EXTENT_FILE}")
    with open(EXTENT_FILE, "r") as f:
        EXTENTS = json.load(f)

    batch_size = 250
    total_batches = (len(EXTENTS) + batch_size - 1) // batch_size

    # Use a single browser instance for all batches
    options = make_options(DOWNLOAD_FOLDER, headless=False)
    service = Service(ChromeDriverManager().install())
    driver = uc.Chrome(options=options, service=service)
    driver.execute_cdp_cmd("Network.enable", {})

    for batch_num in range(total_batches):
        start = batch_num * batch_size
        end = min(start + batch_size, len(EXTENTS))
        batch_extents = EXTENTS[start:end]

        print(f"\n========== 📦 Processing batch {batch_num+1}/{total_batches} "
              f"({len(batch_extents)} extents) ==========")

        qps_token = open_and_get_qps(driver)
        if not qps_token:
            print(f"⚠️ Failed to get QPS token for batch {batch_num+1}, skipping.")
            continue

        qps_file = os.path.join(DOWNLOAD_FOLDER, f"qps_batch_{batch_num+1}.txt")
        with open(qps_file, "w") as f:
            f.write(qps_token)

        download_batch(driver, qps_token, batch_extents, batch_num + 1, REQUEST_TEMPLATE)

        # Wait for downloads to stabilize
        print("⏳ Waiting for downloads to finish...")
        prev_count = 0
        stable_rounds = 0
        max_stable_rounds = 3
        max_wait_time = 120
        start_time = time.time()

        while True:
            files = [f for f in os.listdir(DOWNLOAD_FOLDER) if f.endswith(".json")]
            curr_count = len(files)
            if curr_count == prev_count:
                stable_rounds += 1
            else:
                stable_rounds = 0
                prev_count = curr_count
            if stable_rounds >= max_stable_rounds:
                print(f"✅ Downloads stabilized at {curr_count} files.")
                break
            if time.time() - start_time > max_wait_time:
                print("⚠️ Timeout waiting for downloads — continuing anyway.")
                break
            time.sleep(5)

        print(f"✅ Batch {batch_num+1} done ({curr_count} files total).")
    print("\n✅ All batches processed.")


if __name__ == "__main__":
    capture_qps_and_download()
