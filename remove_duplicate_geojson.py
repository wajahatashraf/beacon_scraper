import os
import json
from config import FOLDER_NAME
import config
import importlib

def remove_duplicate():
    """
    Removes duplicate geometries from the GeoJSON file and saves
    the cleaned version into a subfolder called 'remove_duplicate_geojson'.
    """
    importlib.reload(config)  # reload config to get updated values
    layer_name = config.layer_name
    TABLE_NAME = config.TABLE_NAME
    FOLDER_NAME = config.FOLDER_NAME
    safe_layer_name = layer_name.replace(" ", "_").lower()

    # Final table name: TABLE_NAME + '_' + safe_layer_name
    table_name = f"{TABLE_NAME}_{safe_layer_name}"

    # Create output folder inside your project folder
    output_folder = os.path.join(FOLDER_NAME, layer_name, "remove_duplicate_geojson")
    os.makedirs(output_folder, exist_ok=True)

    # Define input and output paths
    input_file_path = os.path.join(FOLDER_NAME,layer_name, "geojson", f"{table_name}.geojson")
    output_file_path = os.path.join(output_folder, f"{table_name}.geojson")

    # Validate input file existence
    if not os.path.exists(input_file_path):
        print(f"❌ Input file not found: {input_file_path}")
        return

    # Validate file size (check for empty files)
    if os.path.getsize(input_file_path) == 0:
        print(f"❌ Input file is empty: {input_file_path}")
        return

    try:
        # Use standard json library to load GeoJSON
        with open(input_file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ Failed to decode JSON file: {input_file_path}")
        print(f"   Error: {e}")
        return
    except Exception as e:
        print(f"❌ Unexpected error while reading the file: {e}")
        return

    # Ensure it’s a valid FeatureCollection
    if "type" not in data or data["type"] != "FeatureCollection":
        print(f"❌ Invalid GeoJSON: Expected a FeatureCollection.")
        return

    if "features" not in data or not isinstance(data["features"], list):
        print("❌ Invalid GeoJSON: Missing or invalid 'features' key.")
        return

    # Track unique geometries
    unique_geometries = set()
    unique_features = []

    for feature in data["features"]:
        try:
            # Ensure feature has a geometry
            if "geometry" not in feature or not feature["geometry"]:
                print(f"⚠️ Skipping feature with missing geometry: {feature}")
                continue

            key = json.dumps(feature["geometry"], sort_keys=True)

            if key not in unique_geometries:
                unique_geometries.add(key)
                unique_features.append(feature)
        except KeyError as e:
            print(f"⚠️ Skipping feature due to missing data: {e}")
            continue

    # Create a new GeoJSON FeatureCollection
    unique_geojson = {
        "type": "FeatureCollection",
        "features": unique_features
    }

    # Write the cleaned GeoJSON file
    try:
        with open(output_file_path, "w", encoding="utf-8") as f:
            json.dump(unique_geojson, f, indent=2)
    except IOError as e:
        print(f"❌ Failed to write output file: {output_file_path}")
        print(f"   Error: {e}")
        return

    total_unique = len(unique_features)
    print(f"    ✅ Removed duplicates. Saved to: {output_file_path}")
    print(f"    📊 Total unique features: {total_unique}\n")