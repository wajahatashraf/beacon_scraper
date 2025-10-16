import re
import time
import os
import requests
import psycopg2
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from config import DB_CONFIG
import config
import importlib


# ============= STEP 1: Extract SRID =============
def extract_srid():
    importlib.reload(config)  # <-- reload config to get updated values
    BEACON_URL = config.BEACON_URL
    opts = Options()
    opts.add_argument("--start-maximized")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)

    driver.get(BEACON_URL)
    print("	🧩 Getting SRID")
    try:
        # Click "Agree" button if it appears
        wait = WebDriverWait(driver, 15)
        agree_button = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "a.btn.btn-primary.button-1"))
        )
        agree_button.click()
        print("		✅ Clicked 'Agree' button.")
    except Exception:
        print("		⚠️ 'Agree' button not found or already accepted.")

    # Wait for page content to load
    time.sleep(5)

    # Get page source
    page_source = driver.page_source

    # Extract SRID using regex
    srid_match = re.search(r'"Projections":\[\{.*?"SRID":(\d+)', page_source)
    if srid_match:
        srid = srid_match.group(1)
        print(f"		✅ Found SRID: {srid}")
    else:
        print("		    ❌ SRID not found in page source.")

    return srid

    driver.quit()

# ======================================================
# STEP 1.2: Extract Zoning Layer Info
# ======================================================
def extract_zoning_layer_info():
    importlib.reload(config)  # <-- reload config to get updated values
    BEACON_URL = config.BEACON_URL
    FOLDER_NAME = config.FOLDER_NAME
    opts = Options()
    opts.add_argument("--start-maximized")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)

    driver.get(BEACON_URL)
    print("\n	🧩 Getting Zoning Layer Info")
    try:
        # Click "Agree" button if it appears
        wait = WebDriverWait(driver, 15)
        agree_button = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "a.btn.btn-primary.button-1"))
        )
        agree_button.click()
        print("		✅ Clicked 'Agree' button.")
    except Exception:
        print("		⚠️ 'Agree' button not found or already accepted.")

    # Wait for page content to load
    time.sleep(5)

    # Get page source
    page_source = driver.page_source

    # Extract all LayerId / LayerName pairs
    pattern = re.compile(r'{"LayerId":(\d+).*?"LayerName":"(.*?)"', re.DOTALL)
    matches = pattern.findall(page_source)

    zoning_layers = [
        {"LayerId": int(layer_id), "LayerName": re.sub(r'[^a-zA-Z0-9_ ]', '', name.replace("/", " ")).strip()}
        for layer_id, name in matches
        if "zoning" in name.lower()
    ]

    driver.quit()

    if not zoning_layers:
        print("		⚠️ No zoning layers found.")
        return []

    print("		✅ Found zoning layers:")
    for layer in zoning_layers:
        print(f"		   🗂️ {layer['LayerName']} (LayerId: {layer['LayerId']})")

    # Save to JSON file
    os.makedirs(FOLDER_NAME, exist_ok=True)
    layers_path = os.path.join(FOLDER_NAME, "zoning_layers.json")
    with open(layers_path, "w", encoding="utf-8") as f:
        json.dump(zoning_layers, f, indent=2)
    print(f"		💾 Saved zoning layer info to: {layers_path}")

    return zoning_layers

# ============= STEP 2: Get Bounding Box =============
# def get_bounding_box():
#     importlib.reload(config)  # <-- reload config to get updated values
#     COUNTY_NAME = config.COUNTY_NAME
#     print(f"\n	🌍 Fetching bounding box for: {COUNTY_NAME}")
#     url = f"https://nominatim.openstreetmap.org/search?q={COUNTY_NAME}&format=json&polygon_geojson=1"
#     headers = {"User-Agent": "OpenStreetMap Python Script"}
#     r = requests.get(url, headers=headers)
#     r.raise_for_status()
#     data = r.json()
#     if not data:
#         raise ValueError("No results found from Nominatim API.")
#     bbox = data[0]["boundingbox"]  # [south, north, west, east]
#     south, north, west, east = map(float, bbox)
#     print(f"		✅ Bounding Box: South={south}, North={north}, West={west}, East={east}")
#     return south, north, west, east

def get_bounding_box():
    importlib.reload(config)
    COUNTY_NAME = config.COUNTY_NAME


    print(f"\n	🌍 Fetching bounding box for: {COUNTY_NAME} (Google Geocode API)")

    # Build request URL
    url = f"https://user.zoneomics.com/geoCode"
    params = {
        "address": COUNTY_NAME
    }

    # Send request
    r = requests.get(url, params=params)
    r.raise_for_status()
    raw_data = r.json()

    # Handle wrapper if response has extra "data" layer
    if "data" in raw_data and isinstance(raw_data["data"], dict):
        data = raw_data["data"]
    else:
        data = raw_data

    # Extract results
    results = data.get("results", [])
    if not results:
        raise ValueError("No results found from Google Geocoding API.")

    geometry = results[0].get("geometry", {})
    bounds = geometry.get("bounds") or geometry.get("viewport")

    if not bounds:
        raise ValueError("No bounds or viewport found in the Geocoding result.")

    south = bounds["southwest"]["lat"]
    west = bounds["southwest"]["lng"]
    north = bounds["northeast"]["lat"]
    east = bounds["northeast"]["lng"]

    print(f"		✅ Bounding Box: South={south}, North={north}, West={west}, East={east}")
    return south, north, west, east

# ============= STEP 3: Create Table and Grid =============
def create_table_and_grid(srid, south, north, west, east):
    importlib.reload(config)  # <-- reload config to get updated values
    TABLE_NAME = config.TABLE_NAME
    print("\n    🗺️ Creating table and inserting grid...")

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    # Drop and create table
    cur.execute(f"DROP TABLE IF EXISTS {TABLE_NAME} CASCADE;")
    cur.execute(f"""
        CREATE TABLE public.{TABLE_NAME} (
            id SERIAL PRIMARY KEY,
            geom geometry(Polygon, {srid}),
            x_min double precision,
            y_min double precision,
            x_max double precision,
            y_max double precision
        );
    """)
    print(f"		✅ Table '{TABLE_NAME}' created with SRID {srid}.")

    # Compute projected extent
    cur.execute(f"""
        SELECT
            ST_XMin(geom), ST_XMax(geom),
            ST_YMin(geom), ST_YMax(geom)
        FROM (
            SELECT ST_Transform(
                ST_MakeEnvelope({west}, {south}, {east}, {north}, 4326),
                {srid}
            ) AS geom
        ) AS subquery;
    """)
    xmin, xmax, ymin, ymax = cur.fetchone()
    print(f"		✅ Projected Extent: xmin={xmin}, xmax={xmax}, ymin={ymin}, ymax={ymax}")

    # --- AUTO-DETERMINE GRID STEP SIZE ---
    print("	🔍 Finding grid size that produces ~3000 cells...")

    target_count = 3000
    best_step = None
    best_diff = float("inf")

    for step in range(500, 4501, 100):  # try 1500, 1600, ... 3500
        cur.execute(f"""
                WITH grid AS (
                    SELECT
                        x_series AS x_min,
                        y_series AS y_min,
                        x_series + {step} AS x_max,
                        y_series + {step} AS y_max
                    FROM
                        generate_series({xmin}, {xmax}, {step}) AS x_series,
                        generate_series({ymin}, {ymax}, {step}) AS y_series
                )
                SELECT COUNT(*) FROM grid;
            """)
        count = cur.fetchone()[0]
        diff = abs(count - target_count)

        print(f"			step={step} → count={count}")

        if diff < best_diff:
            best_diff = diff
            best_step = step

        if count == target_count:
            break

    print(f"		✅ Selected grid size: {best_step} (closest to 3000 cells)")

    # --- INSERT FINAL GRID USING SELECTED STEP ---
    cur.execute(f"""
            WITH grid AS (
                SELECT
                    x_series AS x_min,
                    y_series AS y_min,
                    x_series + {best_step} AS x_max,
                    y_series + {best_step} AS y_max
                FROM
                    generate_series({xmin}, {xmax}, {best_step}) AS x_series,
                    generate_series({ymin}, {ymax}, {best_step}) AS y_series
            )
            INSERT INTO {TABLE_NAME} (geom)
            SELECT ST_MakeEnvelope(x_min, y_min, x_max, y_max, {srid})
            FROM grid;
        """)
    print("		✅ Grid polygons inserted successfully.")

    # Update bbox columns
    cur.execute(f"""
        UPDATE {TABLE_NAME}
        SET
            x_min = ST_XMin(geom),
            x_max = ST_XMax(geom),
            y_min = ST_YMin(geom),
            y_max = ST_YMax(geom);
    """)
    print("		✅ Bounding box fields updated for each grid cell.")

    # Verify count
    cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAME};")
    count = cur.fetchone()[0]

    conn.commit()
    cur.close()
    conn.close()
    print(f"	    ✅ Inserted {count} grid polygons.")

# ============= STEP 4: Export Grid to JSON =============
def export_grid_to_json():
    importlib.reload(config)  # <-- reload config to get updated values
    TABLE_NAME = config.TABLE_NAME
    FOLDER_NAME = config.FOLDER_NAME
    print("\n🚀 ======  Exporting grid data to JSON ====== ")

    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    cursor.execute(f"SELECT x_min, y_min, x_max, y_max FROM {TABLE_NAME};")
    records = cursor.fetchall()

    record_array = []
    for record in records:
        x_min, y_min, x_max, y_max = record
        record_dict = {
            "minx": x_min,
            "miny": y_min,
            "maxx": x_max,
            "maxy": y_max
        }
        record_array.append(record_dict)

    json_output = json.dumps(record_array, indent=2)

    print(f"	 ✅ Total number of records: {len(record_array)}")

    # Create directory for the table name
    output_dir = os.path.join(os.getcwd(), FOLDER_NAME)
    os.makedirs(output_dir, exist_ok=True)

    # Save JSON file as 'finishnet.json' inside the folder
    filename = os.path.join(output_dir, "finishnet.json")
    with open(filename, "w") as outfile:
        outfile.write(json_output)

    print(f"     💾 JSON file saved as: {filename}")

    cursor.close()
    conn.close()
