import re
import time

from selenium.webdriver import Firefox
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.wait import WebDriverWait
import selenium.webdriver.support.expected_conditions as EC
from selenium.common.exceptions import ElementClickInterceptedException
from selenium.webdriver.common.by import By

from flathunter.logging import logger


def crawl_ref_sqm_price(address: str):
    logger.info(f"Start crawling ref sqm price for address '{address}'")
    multi = 1.5
    # get reference sqm price for given address
    opts = Options()
    opts.headless = True
    driver = Firefox(service=Service(executable_path=r'/home/sven/git_repos/flathunter/geckodriver'), options=opts)
    driver.get('https://www.immowelt.de/immobilienpreise/deutschland/wohnungspreise')
    # hard coded wait for the consent popup to appear
    # popup cannot be properly integrated in webdriver wait because it is inside a shadow-root
    time.sleep(5 * multi)

    try:
        driver.execute_script(
            '''return document.querySelector('div#usercentrics-root').shadowRoot
            .querySelector('button[data-testid="uc-accept-all-button"]')'''
        ).click()  # consent-to-all/click OK-button on privacy popup
        WebDriverWait(driver, 10 * multi).until(EC.presence_of_element_located((By.ID, "addressSearch")))
        input_address = driver.find_element(by=By.CSS_SELECTOR, value="#addressSearch")
        input_address.send_keys(address)
        WebDriverWait(driver, 10 * multi).until(
            EC.presence_of_element_located((By.XPATH, '//*[@id="dropdownMenuContainer"]'))
        )  # wait to locale dropdown list after input

        if re.search(r'[0-9]', address):  # if address is general like a district without specific street address
            first_address_in_dropdown = WebDriverWait(driver, 10 * multi).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="sublistItem_Address_0"]'))
            )
            first_address_in_dropdown.click()
        else:

            last_address_in_dropdown = WebDriverWait(driver, 10 * multi).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="sublistItem_10_0"]'))
            )
            last_address_in_dropdown.click()
        time.sleep(10 * multi)
        WebDriverWait(driver, 10 * multi).until(EC.presence_of_element_located((By.ID, 'squareMeterPrice')))
        sqm_price = int(driver.find_element(By.ID, "squareMeterPrice").text.split(" ")[0].replace(".", ""))

        reference_address = driver.find_element(
            By.XPATH,
            '//*[@id="app"]/div/div[1]/div[1]/div[1]/div/div[2]/div/div[1]/div/div[1]/div/div/div[1]/h1/span[2]'
        ).text.strip()
    except AttributeError as e:
        logger.error(msg=f"{e}\n | Address is: '{address}'")
        sqm_price, reference_address = -1.0, ""
    except ElementClickInterceptedException as e:
        logger.error(msg=f"{e}\n | Address is: '{address}'")
        sqm_price, reference_address = -1.0, ""
    finally:
        driver.quit()

    return sqm_price, reference_address
