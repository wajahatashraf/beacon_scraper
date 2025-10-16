import os
import json
import config
import importlib

def update_missing_features():
    importlib.reload(config)  # <-- reload config to get updated values
    layer_name = config.layer_name
    FOLDER_NAME = config.FOLDER_NAME

    """
    Updates the finishnet.json file to keep only the parcels that are missing
    corresponding .json files inside the 'json' subfolder within FOLDER_NAME.
    """

    # ------------------ Process layer_name ------------------
    safe_layer_name = layer_name.replace(" ", "_").lower()

    # Construct paths
    folder_path = os.path.join(os.getcwd(), FOLDER_NAME, safe_layer_name)
    json_folder_path = os.path.join(folder_path, "json")
    json_file_path = os.path.join(FOLDER_NAME, "finishnet.json")

    # Check paths exist
    if not os.path.exists(json_folder_path):
        print(f"❌ JSON folder not found: {json_folder_path}")
        return

    if not os.path.exists(json_file_path):
        print(f"❌ finishnet.json not found in: {folder_path}")
        return

    # Load finishnet.json
    try:
        with open(json_file_path, "r", encoding="utf-8") as json_file:
            parcel_data = json.load(json_file)
            if not isinstance(parcel_data, list):
                raise ValueError("finishnet.json must contain a list of parcel extents.")
    except Exception as e:
        print(f"❌ Error reading JSON file: {e}")
        return

    # Get existing file names inside /json folder
    existing_files = set(os.listdir(json_folder_path))

    # Find missing parcel extents
    missing_extents = [
        extent for extent in parcel_data
        if f"{extent['minx']}_{extent['maxx']}_{extent['miny']}_{extent['maxy']}.json" not in existing_files
    ]

    # Overwrite finishnet.json with only missing extents
    try:
        with open(json_file_path, "w", encoding="utf-8") as out_file:
            json.dump(missing_extents, out_file, indent=2)

        total_missing = len(missing_extents)

        print(f"    ✅ Total matched : {len(parcel_data) - len(missing_extents)}")
        print(f"    ❌ Total missing : {len(missing_extents)}")
        print(f"    📁 Updated '{json_file_path}' with only missing parcels.\n")

        return total_missing  # <-- return count here


    except Exception as e:
        print(f"❌ Error writing updated JSON: {e}")
