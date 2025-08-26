import time
import requests
import easyocr
from  datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from fake_useragent import UserAgent

class EInvoiceAuthenticator:
    def __init__(self, user:str, password:str):
        self.__user = user
        self.__password = password
        self.authToken = None
        self.session = None
        self.ua = UserAgent().random
        pass

    def getAuthRequestsSession(self) -> requests.Session:
        selenium_cookies, token = self.pesAuth()
        requests_cookies = {cookie['name']: cookie['value'] for cookie in selenium_cookies}
        session = requests.Session()
        session.cookies.update(requests_cookies)
        headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
                'User-Agent': self.ua,
        }
        session.headers = headers
        self.authToken = token
        self.session = session
        return session

    def pesAuth(self):
        # Setup Chrome driver

        options = Options()
        options.add_argument('--headless')  # Run in headless mode
        options.add_argument('--window-size=1280,1024') # The Button is diffrent from moble page!
        options.add_argument(
        "user-agent={ua}"
        )
        options.add_argument("--disable-blink-features=AutomationControlled")
        driver = driver = webdriver.Chrome(options=options) #uc.Chrome() you may need it in some env
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            })
        """
        })
        driver.get("https://www.einvoice.nat.gov.tw/")
        element = WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, 'a[title="登入"]'))
        )
        element.click()

        element = WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.ID, 'mobile_phone'))
        )
        # Enter username and password
        element.send_keys(self.__user)
        driver.find_element(By.ID, "password").send_keys(self.__password)

        while(True):
        # Screenshot captcha image element
            captcha_element = WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, '.input-group-text.code_num'))
            )

            captcha_element.screenshot("dataCaptcha.png")

            # Read captcha using EasyOCR
            reader = easyocr.Reader(['en'], gpu=False)
            result = reader.readtext("dataCaptcha.png", allowlist='0123456789')

            # Print OCR results for verification
            for detection in result:
                print(detection)

            # Assuming first result is correct
            captcha_text = result[0][1]

            old_url = driver.current_url

            driver.find_element(By.ID, "captcha").send_keys(captcha_text)
            driver.find_element(By.ID, "submitBtn").click()

            time.sleep(3)

            new_url = driver.current_url
            if new_url != old_url:
                break
            else:
                driver.find_element(By.CSS_SELECTOR, ".btn.btn-outline-secondary.icon").click()

            # Wait to observe result before closing
        token = driver.execute_script("return sessionStorage.getItem('saveToken');")
        selenium_cookies = driver.get_cookies()
        driver.quit()
        return selenium_cookies, token

    def getCarrierList(self, max_retries:int=2) -> dict:
        url = "https://service-mc.einvoice.nat.gov.tw/btc/cloud/api/btc502w/getCarrierList"
        if self.session is None:
            self.getAuthRequestsSession()
        for attempt in range(max_retries):
            response = self.session.get(url)
            if response.status_code == 200:
                return response.json()
            else:
                # Re-authenticate and retry
                self.session = self.getAuthRequestsSession()
        return {'Failed': 'Failed to retrieve carrier list after retries.'}

    def getSearchCarrierInvoiceListJWT(self, searchStartDate:datetime, searchEndDate:datetime, max_retries:int=2) -> str: #returns JWT token
        url = "https://service-mc.einvoice.nat.gov.tw/btc/cloud/api/btc502w/getSearchCarrierInvoiceListJWT"
        print("Try to Searching. Start at"+searchStartDate.isoformat()+" end at"+searchStartDate.isoformat())

        searchStartDate = searchStartDate.replace(hour=15, minute=5, second=23, microsecond=222000) #if not the api may fail
        searchEndDate = searchEndDate.replace(hour=15, minute=5, second=23, microsecond=222000)
        
        if self.session is None:
            self.getAuthRequestsSession()

        data = {
            "cardCode": "",
            "carrierId2": "",
            "searchEndDate": searchEndDate.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "searchStartDate": searchStartDate.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "invoiceStatus": "all",
            "isSearchAll": "true"
        }
        for attempt in range(max_retries):
            response = self.session.post(
                url,
                json=data
            )
            if response.status_code == 200:
                return response.text
            else:
                # Re-authenticate and retry
                self.session = self.getAuthRequestsSession()
        return ''
        
    def searchCarrierInvoice(self, token:str,page=0,size=10, max_retries:int=2) -> dict:
        url = f"https://service-mc.einvoice.nat.gov.tw/btc/cloud/api/btc502w/searchCarrierInvoice?page={page}&size={size}"
        if self.session is None:
            self.getAuthRequestsSession()
        payload = {
            "token": token
        }
        for attempt in range(max_retries): 
            response = self.session.post(
                url,
                json=payload
            )
            if response.status_code == 200:
                return response.json()
            else:
                # Re-authenticate and retry
                self.session = self.getAuthRequestsSession()
        return {'Failed': 'Failed to search carrier invoice after retries.'}
    
    def getCarrierInvoiceData(self, token:str, max_retries:int=2) -> dict:
        url = "https://service-mc.einvoice.nat.gov.tw/btc/cloud/api/common/getCarrierInvoiceData"
        if self.session is None:
            self.getAuthRequestsSession()

        for attempt in range(max_retries):
            response = self.session.post(
                url,
                data = token # Yes it is a string, not json or dict
            )
            print(response.text)
            if response.status_code == 200:
                return response.json()
            else:
                self.session = self.getAuthRequestsSession()
        return {'Failed:getCarrierInvoiceData()': 'Failed to retrieve carrier invoice data after retries.'}

    def getCarrierInvoiceDetail(self, token:str,page:int=0,size:int=10, max_retries:int=2) -> dict:
        url = f"https://service-mc.einvoice.nat.gov.tw/btc/cloud/api/common/getCarrierInvoiceDetail?page={page}&size={size}"
        if self.session is None:
            self.getAuthRequestsSession()
        
        for attempt in range(max_retries):
            response = self.session.post(
                url,
                data = token # Yes it is a string, not json or dict
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                self.session = self.getAuthRequestsSession()
        return {'Failed:getCarrierInvoiceDetail()': 'Failed to retrieve carrier invoice detail after retries.'}

