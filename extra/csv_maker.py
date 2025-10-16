import cloudscraper
import csv
import sys

url = "https://beacon.schneidercorp.com/api/globalsearch/framework"
output_csv = "iowa_counties.csv"

# Create a Cloudflare-bypassing session
scraper = cloudscraper.create_scraper(browser={"browser": "chrome", "platform": "windows", "mobile": False})

try:
    response = scraper.get(url, timeout=15)
    response.raise_for_status()
    data = response.json()
except Exception as e:
    print(f"❌ Error fetching or parsing API: {e}")
    print(response.text[:500])
    sys.exit(1)

# Extract state data
states = data.get("States", [])
indiana_data = next((state for state in states if state.get("Name") == "Iowa"), None)

if not indiana_data:
    print("❌ Indiana not found in API response.")
    sys.exit(1)

# Build CSV rows
rows = []
for app in indiana_data.get("Apps", []):
    app_id = app["ID"]
    display_name = app["DisplayName"].replace(",", "")
    website_url = f"https://beacon.schneidercorp.com/Application.aspx?AppID={app_id}"
    rows.append([website_url, display_name.strip()])

# Write to CSV
with open(output_csv, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["website_url", "county_name"])
    writer.writerows(rows)

print(f"✅ CSV created successfully: {output_csv}")
