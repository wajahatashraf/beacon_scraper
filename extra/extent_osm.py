import requests
import csv
import time

# Input CSV file
input_csv = "indiana_counties.csv"

# Nominatim endpoint
BASE_URL = "https://nominatim.openstreetmap.org/search"

# Headers required by Nominatim
HEADERS = {"User-Agent": "OpenStreetMap Python Script"}

failed = []  # to store counties that failed

def get_bounding_box(county_name):
    """Fetch bounding box for a county name from Nominatim."""
    try:
        params = {
            "q": county_name,
            "format": "json",
            "polygon_geojson": 1
        }
        r = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
        if not data:
            raise ValueError("No results found.")
        bbox = data[0]["boundingbox"]
        south, north, west, east = map(float, bbox)
        print(f"✅ {county_name} → South={south}, North={north}, West={west}, East={east}")
        return (south, north, west, east)
    except Exception as e:
        print(f"❌ Failed for {county_name}: {e}")
        failed.append(county_name)
        return None

# Read CSV and process each county
with open(input_csv, newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        county_name = row["county_name"]
        get_bounding_box(county_name)
        time.sleep(1)  # ✅ Be polite to the API (avoid rate-limits)

# Show failed ones
if failed:
    print("\n⚠️ These counties returned no results or errors:")
    for c in failed:
        print(" -", c)
else:
    print("\n🎉 All counties returned valid results!")
