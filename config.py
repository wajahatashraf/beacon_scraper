# ================= CONFIGURATION ================= #

DB_CONFIG = {
    "host": "localhost",
    "port": "5432",
    "dbname": "scraper",
    "user": "postgres",
    "password": "admin123"
}

# ===== Project / Beacon Config ===== #
BEACON_URL = "https://beacon.schneidercorp.com/Application.aspx?AppID=578"
COUNTY_NAME = "Tippecanoe County IN"
TABLE_NAME = COUNTY_NAME.lower().replace(" ", "_")  # cass_county_il
FOLDER_NAME = COUNTY_NAME.lower().replace(" ", "_")  # cass_county_il
layer_id = 42828
layer_name = 'zoning__udo_update'
