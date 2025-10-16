import csv
import psycopg2
import requests
import importlib

# =========================
# CONFIGURATION
# =========================
CSV_FILE = "iowa_counties.csv"  # Path to your CSV file
SRID = 2915  # Target projection SRID (example: Indiana State Plane East)
DB_CONFIG = {
    "dbname": "postgres",
    "user": "postgres",
    "password": "admin123",
    "host": "localhost",
    "port": 5432
}


# # =========================
# # FUNCTION: Get bounding box from Nominatim
# # =========================
# def get_bounding_box(county_name):
#     print(f"\n🌍 Fetching bounding box for: {county_name}")
#     url = f"https://nominatim.openstreetmap.org/search?q={county_name}&format=json&polygon_geojson=1"
#     headers = {"User-Agent": "OpenStreetMap Python Script"}
#     r = requests.get(url, headers=headers)
#     r.raise_for_status()
#     data = r.json()
#
#     if not data:
#         raise ValueError(f"No results found for {county_name}")
#
#     bbox = data[0]["boundingbox"]  # [south, north, west, east]
#     south, north, west, east = map(float, bbox)
#     print(f"✅ Bounding Box: South={south}, North={north}, West={west}, East={east}")
#     return south, north, west, east

def get_bounding_box(COUNTY_NAME):


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
# =========================
# FUNCTION: Compute projected extent & test grid counts
# =========================
def test_grid_counts(conn, county_name, bbox, srid=SRID):
    south, north, west, east = bbox
    cur = conn.cursor()

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
    print(f"✅ Projected Extent: xmin={xmin}, xmax={xmax}, ymin={ymin}, ymax={ymax}")

    # Loop through step sizes and count grid cells
    counts = {}
    for step in range(500, 4500, 100):
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
        counts[step] = count
        print(f"    step={step} → count={count}")

    cur.close()
    return counts


# =========================
# MAIN SCRIPT
# =========================
def main():
    # Connect to PostgreSQL
    conn = psycopg2.connect(**DB_CONFIG)
    constant_counties = []

    # Read CSV and process each county
    with open(CSV_FILE, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            county_name = row["county_name"].strip()
            try:
                bbox = get_bounding_box(county_name)
                counts = test_grid_counts(conn, county_name, bbox)

                # Check if all counts == 1
                if all(c == 1 for c in counts.values()):
                    print(f"🎯 {county_name} → All counts are 1 ✅")
                    constant_counties.append(county_name)
                else:
                    print(f"❌ {county_name} → Not all counts are 1")

            except Exception as e:
                print(f"⚠️ Error processing {county_name}: {e}")

    # Close connection
    conn.close()

    # Print summary
    print("\n========== SUMMARY ==========")
    if constant_counties:
        print("Counties with all counts = 1:")
        for name in constant_counties:
            print("  •", name)
    else:
        print("No counties have constant count = 1 for all step sizes.")


# =========================
# ENTRY POINT
# =========================
if __name__ == "__main__":
    main()
