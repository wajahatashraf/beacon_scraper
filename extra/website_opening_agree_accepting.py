# open_site_click_agree_network.py
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time

URL = "https://beacon.schneidercorp.com/Application.aspx?AppID=55&LayerID=375&PageTypeID=1&PageID=916"

def open_site_and_click_agree():
    opts = Options()
    opts.add_argument("--start-maximized")
    opts.add_argument("--auto-open-devtools-for-tabs")  # open DevTools
    opts.add_experimental_option("detach", True)  # keep Chrome open after script
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)

    driver.get(URL)

    try:
        # Wait for the "Agree" button and click it
        wait = WebDriverWait(driver, 15)
        agree_button = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "a.btn.btn-primary.button-1"))
        )
        agree_button.click()
        print("✅ Clicked 'Agree' button successfully.")
    except Exception as e:
        print("⚠️ Couldn't click 'Agree' button:", e)

    # Wait a bit for DevTools to open
    time.sleep(3)

    # Simulate Ctrl+6 to switch to Network tab
    actions = ActionChains(driver)
    actions.key_down(Keys.CONTROL).send_keys("6").key_up(Keys.CONTROL).perform()
    print("✅ Switched to Network tab (DevTools).")

    input("Press Enter to close browser...")
    driver.quit()

if __name__ == "__main__":
    open_site_and_click_agree()
