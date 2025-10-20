import csv
import os
import time
from table_creater import extract_srid, get_bounding_box, create_table_and_grid, export_grid_to_json, extract_zoning_layer_info
from python_java import capture_qps_and_download
from db_insert_json import db_insert
from verify_record import update_missing_features
from geojson import export_table_to_geojson
from remove_duplicate_geojson import remove_duplicate
import traceback


def update_config(beacon_url, county_name):
    """Update BEACON_URL and COUNTY_NAME in config.py"""
    config_file_path = os.path.join(os.getcwd(), "config.py")
    with open(config_file_path, "r+") as f:
        lines = f.readlines()
        for i, line in enumerate(lines):
            if line.strip().startswith("BEACON_URL"):
                lines[i] = f'BEACON_URL = "{beacon_url}"\n'
            elif line.strip().startswith("COUNTY_NAME"):
                lines[i] = f'COUNTY_NAME = "{county_name}"\n'
        f.seek(0)
        f.writelines(lines)
        f.truncate()
    print(f"✅ Updated config.py: BEACON_URL={beacon_url}, COUNTY_NAME='{county_name}'")

def log_error_to_csv(csv_file, county_name, error_message):
    """Update error_message in the same CSV (no temp file)."""
    try:
        rows = []
        fieldnames = []

        # ✅ Read existing rows
        if os.path.exists(csv_file):
            with open(csv_file, newline="", encoding="utf-8-sig") as infile:
                reader = csv.DictReader(infile)
                fieldnames = reader.fieldnames or []
                rows = list(reader)

        # ✅ Ensure required columns
        if "county_name" not in fieldnames:
            fieldnames.append("county_name")
        if "error_message" not in fieldnames:
            fieldnames.append("error_message")

        # ✅ Update or append the county row
        county_found = False
        for row in rows:
            if row.get("county_name", "").strip().lower() == county_name.strip().lower():
                row["error_message"] = error_message
                county_found = True
            elif "error_message" not in row:
                row["error_message"] = ""

        if not county_found:
            rows.append({"county_name": county_name, "error_message": error_message})

        # ✅ Write back to same CSV
        with open(csv_file, "w", newline="", encoding="utf-8") as outfile:
            writer = csv.DictWriter(outfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        print(f"⚠️ Logged error for {county_name}: {error_message}")

    except Exception as log_err:
        print(f"❌ Failed to log error for {county_name}: {log_err}")



def main():
    csv_file = "county_urls.csv"  # change filename if needed
    if not os.path.exists(csv_file):
        print(f"❌ CSV file '{csv_file}' not found.")
        return

    with open(csv_file, newline="", encoding="utf-8-sig") as csvfile:
        reader = csv.DictReader(csvfile)

        normalized_fieldnames = {name.strip().lower().replace(" ", "_"): name for name in reader.fieldnames}
        if "website_url" not in normalized_fieldnames or "county_name" not in normalized_fieldnames:
            print(f"❌ CSV must have 'website_url' and 'county_name' columns. Found: {reader.fieldnames}")
            return

        for row in reader:
            beacon_url = row[normalized_fieldnames["website_url"]].strip()
            county_name = row[normalized_fieldnames["county_name"]].strip()

            try:
                print(f"\n🚀 ====== Processing County: {county_name} ======")
                update_config(beacon_url, county_name)

                # === Step 1: Making Table ===
                print("🚀  ====== Starting Making Table ======")
                srid = extract_srid()

                zoning_layers = extract_zoning_layer_info()
                if not zoning_layers:
                    message = "No zoning layers found."
                    print(f"\t⚠️ {message}")
                    log_error_to_csv(csv_file, county_name, message)
                    print(f"🎉 Completed county: {county_name}\n")
                    continue

                south, north, west, east = get_bounding_box()
                create_table_and_grid(srid, south, north, west, east)

                for layer in zoning_layers:
                    layer_id = layer["LayerId"]
                    layer_name = layer["LayerName"].replace(" ", "_").lower()

                    print(f"\n🚀 ====== Processing Layer: {layer_name} (ID: {layer_id}) ======")

                    # Update config.py for this layer
                    config_file_path = os.path.join(os.getcwd(), "config.py")
                    with open(config_file_path, "r+") as f:
                        lines = f.readlines()
                        for i, line in enumerate(lines):
                            if line.strip().startswith("layer_id"):
                                lines[i] = f"layer_id = {layer_id}\n"
                            elif line.strip().startswith("layer_name"):
                                lines[i] = f"layer_name = '{layer_name}'\n"
                        f.seek(0)
                        f.writelines(lines)
                        f.truncate()
                    print(f"    ✅ Updated config.py: layer_id={layer_id}, layer_name='{layer_name}'")

                    export_grid_to_json()

                    # Step 4: Download JSON files for this layer
                    print("\n🚀 ====== Starting Downloading JSON Files ======")
                    capture_qps_and_download()

                    # Step 5: Check for missing parcel files
                    print("🚀 Checking for missing parcel files...")
                    attempt = 1
                    while True:
                        print(f"\n🔎 Attempt #{attempt}: Checking for missing files...")
                        missing_count = update_missing_features()

                        if missing_count > 0:
                            print(f"🔁 Found {missing_count} missing files — retrying download...")
                            capture_qps_and_download()
                            attempt += 1
                            time.sleep(3)
                        else:
                            print("✅ No missing parcels found. Skipping re-download.")
                            break

                    # Step 6: Insert JSON data into DB
                    print("🚀 ====== INSERTING Data OF JSON Files IN DB ====== ")
                    db_insert(srid)

                    # Step 7: Export DB table to GeoJSON
                    print("🚀 ====== Making GeoJSON From DB ====== ")
                    export_table_to_geojson()

                    # Step 8: Remove duplicate geometries
                    print("🚀 ====== Removing Duplicate geom ====== ")
                    remove_duplicate()

                    print(f"✅ Finished processing layer: {layer_name}\n")

                print(f"🎉 Completed county: {county_name}\n")

            except Exception as e:
                # Capture full traceback
                error_message = f"{type(e).__name__}: {str(e)}"
                print(f"❌ Error processing {county_name}: {error_message}")
                traceback.print_exc()

                # Log to CSV
                log_error_to_csv(csv_file, county_name, error_message)

                # Continue with next county
                continue

    print("🎉 All counties processed successfully (errors logged in CSV where applicable)!")



if __name__ == "__main__":
    main()
