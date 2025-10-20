import os
import json
import psycopg2
from qmap_scraper.config import DB_CONFIG
import qmap_scraper.config
import importlib
from bs4 import BeautifulSoup
import re  # Import re module here


# ========================================
#  Database Connection
# ========================================
def connect_to_db():
    """Connects to PostgreSQL using settings from config.py"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        print("    ✅ Database connection established.")
        return conn
    except Exception as e:
        print(f"❌ Error connecting to database: {e}")
        return None


# ========================================
#  Table & Column Management
# ========================================
def add_column_to_table(conn, column_name,FINAL_TABLE_NAME):
    try:
        with conn.cursor() as cur:
            # Check if the column already exists
            cur.execute(f"""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = '{FINAL_TABLE_NAME}' AND column_name = %s;
            """, (column_name,))
            if cur.fetchone():
                return

            # Add the new column
            cur.execute(f"""
                ALTER TABLE {FINAL_TABLE_NAME}
                ADD COLUMN {column_name} TEXT;
            """)
            conn.commit()
            print(f"    ✅ Column '{column_name}' added to table '{FINAL_TABLE_NAME}'.")
    except Exception as e:
        print(f"❌ Error adding column '{column_name}': {e}")


def create_table(conn,FINAL_TABLE_NAME):
    try:
        with conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {FINAL_TABLE_NAME} CASCADE;")
            conn.commit()
            print(f"    ⚠️ Existing table '{FINAL_TABLE_NAME}' dropped.")
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {FINAL_TABLE_NAME}(
                    id SERIAL PRIMARY KEY,
                    geom GEOMETRY(MULTIPOLYGON, 4326)
                );
            """)
            conn.commit()
            print(f"    ✅ Table '{FINAL_TABLE_NAME}' created or already exists.")
    except Exception as e:
        print(f"❌ Error creating table: {e}")

def sanitize_key(key):
    """
    Function to sanitize column names to comply with SQL naming conventions.
    - Replace invalid characters with underscores.
    - Prefix column names that start with numbers with 'col_'.
    """
    key = re.sub(r'\W+', '_', key)  # Replace non-alphanumeric characters with underscores
    if key[0].isdigit():  # If the key starts with a digit, prefix it with 'col_'
        key = f"col_{key}"
    return key.lower()
# ========================================
#  Data Insertion
# ========================================
def process_json_file(file_path, conn, srid, insert_counter,FINAL_TABLE_NAME):
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            data = json.load(file)
            for item in data.get("d", []):
                geom = item.get("WktGeometry")
                tip_html = item.get("TipHtml", "")
                result_data = item.get("ResultData", [])

                # ============================
                # Extract dynamic fields
                # ============================
                dynamic_columns = {}

                # Case 1: from ResultData array
                if result_data:
                    for field in result_data:
                        key = field.get("Key", "").strip().replace(" ", "_").lower()
                        value = field.get("Value")
                        dynamic_columns[key] = value

                # Case 2: from TipHtml (fallback)
                elif tip_html:
                    from bs4 import BeautifulSoup
                    import html

                    # ======================
                    # 🆕 NEW CASES (before main logic)
                    # ======================
                    if (
                            'Zoning:' in tip_html
                            and '<b>' in tip_html
                            and '<a href' in tip_html
                    ):
                        # Example:
                        # <div>Zoning: <b>I-1</b></div>
                        # <div><a href="https://...">View I-1 Ordinance</a></div>
                        soup = BeautifulSoup(tip_html, "html.parser")
                        zoning_div = soup.find("div")
                        link_div = zoning_div.find_next_sibling("div") if zoning_div else None

                        # Extract zoning value
                        if zoning_div and zoning_div.find("b"):
                            zoning_value = zoning_div.find("b").get_text(strip=True)
                            if zoning_value:
                                dynamic_columns["zoning"] = zoning_value

                        # Extract ordinance link
                        if link_div and link_div.find("a") and link_div.find("a").get("href"):
                            dynamic_columns["ordinance_link"] = link_div.find("a")["href"].strip()

                    elif (
                            tip_html.strip().startswith("<div>")
                            and "</div>" in tip_html
                            and " " not in BeautifulSoup(tip_html, "html.parser").get_text(strip=True)
                            and ":" not in tip_html
                            and "<b>" not in tip_html
                            and "<a" not in tip_html
                    ):
                        # Example: <div>C1</div>
                        soup = BeautifulSoup(tip_html, "html.parser")
                        value = soup.get_text(strip=True)
                        if value:
                            dynamic_columns["tip_value"] = value

                    elif  "<" in tip_html and ">" in tip_html:
                        soup = BeautifulSoup(tip_html, "html.parser")
                        divs = soup.find_all("div")

                        # ======================
                        # Case 1: Handle <div> blocks
                        # ======================
                        if divs:
                            for div in divs:
                                # Loop through all <b> tags inside the div
                                b_tags = div.find_all("b")
                                if b_tags:
                                    for b_tag in b_tags:
                                        key = sanitize_key(
                                            b_tag.get_text(strip=True).replace(":", "").replace(" ", "_"))

                                        # Extract everything after this <b> until the next <b> or <br>
                                        value_parts = []
                                        for sibling in b_tag.next_siblings:
                                            if getattr(sibling, "name", None) == "b":  # stop if next <b> starts
                                                break
                                            if getattr(sibling, "name", None) == "br":
                                                continue
                                            text = str(sibling).strip()
                                            if text:
                                                value_parts.append(html.unescape(text))
                                        value = " ".join(value_parts).replace("\xa0", "").strip()
                                        if value:
                                            dynamic_columns[key] = value
                                    continue

                                # Case 2: "Label: Value" (plain text inside div)
                                text = div.get_text(" ", strip=True)
                                separator = ":" if ":" in text else "=" if "=" in text else None
                                if separator:
                                    parts = text.split(separator, 1)
                                    key = sanitize_key(parts[0].strip().replace(" ", "_"))
                                    value = parts[1].strip()

                                    # Extract link if present
                                    a_tag = div.find("a")
                                    if a_tag and a_tag.get("href"):
                                        value = a_tag["href"].strip()

                                    if value:
                                        dynamic_columns[key] = value

                                plain_text = div.get_text(strip=True)
                                if plain_text:
                                    dynamic_columns["tip_value"] = plain_text

                        # ======================
                        # Case 3: Standalone <b> tags outside <div>
                        # ======================
                        elif soup.find("b"):
                            for b_tag in soup.find_all("b"):
                                key = sanitize_key(b_tag.get_text(strip=True).replace(":", "").replace(" ", "_"))
                                value = b_tag.next_sibling
                                if value:
                                    value = html.unescape(str(value)).strip().replace("\xa0", "").replace("\n", "")
                                    if value:
                                        dynamic_columns[key] = value

                        # ======================
                        # Case 4: Plain text with <br> separators (no <div> or <b>)
                        # ======================
                        else:
                            text_parts = []
                            for elem in soup.stripped_strings:
                                text_parts.append(elem)

                            for line in text_parts:
                                # Look for key-value pairs separated by ':' or '='
                                separator = "=" if "=" in line else ":" if ":" in line else None
                                if not separator:
                                    continue

                                parts = line.split(separator, 1)
                                key = sanitize_key(parts[0].strip().replace(" ", "_"))
                                value = parts[1].strip()

                                # Handle links (like "View: <a href=...>")
                                a_tag = soup.find("a")
                                if a_tag and key.startswith("view") and a_tag.get("href"):
                                    value = a_tag["href"].strip()

                                if value:
                                    dynamic_columns[key] = value

                    else:
                        # ======================
                        # Fallback for plain text TipHtml
                        # ======================
                        for line in tip_html.splitlines():
                            if "=" in line:
                                key, value = line.split("=", 1)
                                key = sanitize_key(key.strip().replace(" ", "_"))
                                value = value.strip()
                                dynamic_columns[key] = value

                # ============================
                # Skip if no geometry
                # ============================
                if not geom:
                    print(f"⚠️ Skipping feature without geometry in {file_path}")
                    continue

                # ============================
                # Ensure table has columns
                # ============================
                for column_name in dynamic_columns.keys():
                    add_column_to_table(conn, column_name,FINAL_TABLE_NAME)

                # ============================
                # Try inserting
                # ============================
                success = insert_into_db(conn, geom, srid, dynamic_columns,FINAL_TABLE_NAME)
                if success:
                    insert_counter[0] += 1

    except json.JSONDecodeError as e:
        print(f"❌ JSON decode error in {file_path}: {e}")
        conn.rollback()
    except Exception as e:
        print(f"❌ Error processing {file_path}: {e}")
        conn.rollback()



def insert_into_db(conn, geom, srid, dynamic_columns,FINAL_TABLE_NAME):
    try:
        column_names = ", ".join(dynamic_columns.keys())
        placeholders = ", ".join(["%s"] * len(dynamic_columns))
        values = list(dynamic_columns.values())

        if column_names:
            column_names = f"geom, {column_names}"
            placeholders = f"ST_Transform(ST_GeomFromText(%s, {srid}), 4326), {placeholders}"
        else:
            column_names = "geom"
            placeholders = f"ST_Transform(ST_GeomFromText(%s, {srid}), 4326)"

        values = [geom] + values

        with conn.cursor() as cur:
            cur.execute(f"""
                INSERT INTO {FINAL_TABLE_NAME} ({column_names})
                VALUES ({placeholders});
            """, values)
        conn.commit()
        return True

    except psycopg2.Error as e:
        conn.rollback()  # ✅ Important fix
        print(f"❌ Database error inserting geometry: {e.pgerror.strip() if e.pgerror else e}")
        return False
    except Exception as e:
        conn.rollback()
        print(f"❌ Unexpected error inserting data: {e}")
        return False


# ========================================
#  Main Function
# ========================================
def db_insert(srid):
    layer_name = 'zoning'
    COUNTY_NAME = "Worth County IA"
    FOLDER_NAME = COUNTY_NAME.lower().replace(" ", "_")  # cass_county_il
    TABLE_NAME =COUNTY_NAME.lower().replace(" ", "_")  # cass_county_il
    safe_layer_name = layer_name.replace(" ", "_").lower()
    FINAL_TABLE_NAME = f"{TABLE_NAME}_{safe_layer_name}"
    JSON_FOLDER = os.path.join(os.getcwd(), FOLDER_NAME, layer_name, "json")

    conn = connect_to_db()
    if not conn:
        return

    create_table(conn,FINAL_TABLE_NAME)
    insert_counter = [0]  # Use list for mutability

    # Process all JSON files
    for filename in os.listdir(JSON_FOLDER):
        if filename.endswith(".json"):
            file_path = os.path.join(JSON_FOLDER, filename)
            process_json_file(file_path, conn, srid, insert_counter,FINAL_TABLE_NAME)

    conn.close()
    print(f"    ✅ Total records inserted: {insert_counter[0]}")


if __name__ == "__main__":
    srid = 102675
    db_insert(srid)
