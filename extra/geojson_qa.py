import os
import json

# Path to your main folder
base_dir = r"C:\Users\user\Desktop\Montgomery County IN"

# Loop through all subfolders and files
for root, dirs, files in os.walk(base_dir):
    for file in files:
        if file.endswith(".geojson"):
            file_path = os.path.join(root, file)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                    # Make sure it's a FeatureCollection
                    if data.get("type") == "FeatureCollection":
                        for feature in data.get("features", []):
                            # Check if properties is empty
                            if feature.get("properties") == {}:
                                print(f"Empty properties found in: {file_path}")
                                break  # stop checking further features in this file
            except Exception as e:
                print(f"Error reading {file_path}: {e}")
