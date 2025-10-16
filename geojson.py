import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from config import DB_CONFIG
import config
import importlib


def export_table_to_geojson():
    """
    Exports a PostgreSQL table (with geom in SRID 4326)
    to a GeoJSON FeatureCollection file.
    """
    importlib.reload(config)  # reload config to get updated values
    layer_name = config.layer_name
    TABLE_NAME = config.TABLE_NAME
    FOLDER_NAME = config.FOLDER_NAME

    safe_layer_name = layer_name.replace(" ", "_").lower()

    # Final table name: TABLE_NAME + '_' + safe_layer_name
    table_name = f"{TABLE_NAME}_{safe_layer_name}"

    # Output folder and file
    output_folder = os.path.join(os.getcwd(), FOLDER_NAME, layer_name, "geojson")
    os.makedirs(output_folder, exist_ok=True)
    output_file = os.path.join(output_folder, f"{table_name}.geojson")

    try:
        # Connect to database
        print(" 🔌 Connecting to database...")
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Fetch rows with geometry as GeoJSON
        print(f"    📦 Fetching data from table '{table_name}'...")
        query = f"""
            SELECT *, ST_AsGeoJSON(geom)::json AS geometry
            FROM {table_name};
        """
        cur.execute(query)
        rows = cur.fetchall()

        features = []
        for row in rows:
            geom = row.pop("geometry", None)
            row.pop("geom", None)
            row.pop("id", None)

            if geom:
                features.append({
                    "type": "Feature",
                    "geometry": geom,
                    "properties": row
                })

        geojson = {
            "type": "FeatureCollection",
            "features": features
        }

        # Write GeoJSON file
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(geojson, f, indent=2)

        print(f"    ✅ Exported {len(features)} features to '{output_file}'")

    except Exception as e:
        print(f"    ❌ Error exporting GeoJSON: {e}")

    finally:
        if 'conn' in locals():
            cur.close()
            conn.close()


if __name__ == "__main__":
    export_table_to_geojson()
