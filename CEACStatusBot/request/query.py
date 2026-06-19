import random
import time

import requests
from bs4 import BeautifulSoup

from CEACStatusBot.captcha import CaptchaHandle, OnnxCaptchaHandle

# (connect timeout, read timeout) for every HTTP call so a hung connection can
# never wedge the scheduled job forever.
HTTP_TIMEOUT = (10, 30)

CAPTCHA_IMG_ID = "c_status_ctl00_contentplaceholder1_defaultcaptcha_CaptchaImage"
STATUS_PREFIX = "ctl00_ContentPlaceHolder1_ucApplicationStatusView_"


def query_status(location, application_num, passport_number, surname, captchaHandle: CaptchaHandle = OnnxCaptchaHandle("captcha.onnx")):
    result = {"success": False}

    for failCount in range(5):
        if failCount > 0:
            # Randomised back-off so retries don't look like clockwork.
            backupTime = random.uniform(4, 9)
            print(f"Retrying... Attempt {failCount + 1} / 5 in {backupTime:.1f}s")
            time.sleep(backupTime)

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
                "Accept-Encoding": "gzip, deflate",
                "Accept-Language": "en,zh-CN;q=0.9,zh;q=0.8",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Host": "ceac.state.gov",
            }

            session = requests.Session()
            ROOT = "https://ceac.state.gov"

            r = session.get(url=f"{ROOT}/ceacstattracker/status.aspx?App=NIV", headers=headers, timeout=HTTP_TIMEOUT)
            soup = BeautifulSoup(r.text, features="lxml")

            # Captcha image
            captcha = soup.find(name="img", id=CAPTCHA_IMG_ID)
            if captcha is None or not captcha.get("src"):
                print("Captcha image not found on page; retrying.")
                continue
            img_resp = session.get(ROOT + captcha["src"], timeout=HTTP_TIMEOUT)
            captcha_num = captchaHandle.solve(img_resp.content)
            print(f"Captcha solved: {captcha_num}")

            # Location dropdown -> the option value whose visible text contains `location`
            location_dropdown = soup.find("select", id="Location_Dropdown")
            if location_dropdown is None:
                print("Location dropdown not found on page; retrying.")
                continue
            location_value = None
            for option in location_dropdown.find_all("option"):
                if location in option.get_text():
                    location_value = option.get("value")
                    break
            if not location_value:
                print(f"Location '{location}' not found in dropdown options.")
                return {"success": False}

            def update_from_current_page(cur_page, name, data):
                ele = cur_page.find(name="input", attrs={"name": name})
                if ele and ele.get("value") is not None:
                    data[name] = ele["value"]

            data = {
                "ctl00$ToolkitScriptManager1": "ctl00$ContentPlaceHolder1$UpdatePanel1|ctl00$ContentPlaceHolder1$btnSubmit",
                "ctl00_ToolkitScriptManager1_HiddenField": ";;AjaxControlToolkit, Version=4.1.40412.0, Culture=neutral, PublicKeyToken=28f01b0e84b6d53e:en-US:acfc7575-cdee-46af-964f-5d85d9cdcf92:de1feab2:f9cec9bc:a67c2700:f2c8e708:8613aea7:3202a5a2:ab09e3fe:87104b7c:be6fb298",
                "__EVENTTARGET": "ctl00$ContentPlaceHolder1$btnSubmit",
                "__EVENTARGUMENT": "",
                "__LASTFOCUS": "",
                "__VIEWSTATE": "8GJOG5GAuT1ex7KX3jakWssS08FPVm5hTO2feqUpJk8w5ukH4LG/o39O4OFGzy/f2XLN8uMeXUQBDwcO9rnn5hdlGUfb2IOmzeTofHrRNmB/hwsFyI4mEx0mf7YZo19g",
                "__VIEWSTATEGENERATOR": "DBF1011F",
                "__VIEWSTATEENCRYPTED": "",
                "ctl00$ContentPlaceHolder1$Visa_Application_Type": "NIV",
                "ctl00$ContentPlaceHolder1$Location_Dropdown": location_value,
                "ctl00$ContentPlaceHolder1$Visa_Case_Number": application_num,
                "ctl00$ContentPlaceHolder1$Captcha": captcha_num,
                "ctl00$ContentPlaceHolder1$Passport_Number": passport_number,
                "ctl00$ContentPlaceHolder1$Surname": surname,
                "LBD_VCID_c_status_ctl00_contentplaceholder1_defaultcaptcha": "a81747f3a56d4877bf16e1a5450fb944",
                "LBD_BackWorkaround_c_status_ctl00_contentplaceholder1_defaultcaptcha": "1",
                "__ASYNCPOST": "true",
            }

            for field in ["__VIEWSTATE", "__VIEWSTATEGENERATOR", "LBD_VCID_c_status_ctl00_contentplaceholder1_defaultcaptcha"]:
                update_from_current_page(soup, field, data)

            # Human-like pause between loading the page and submitting the form.
            time.sleep(random.uniform(2.0, 5.0))

            r = session.post(url=f"{ROOT}/ceacstattracker/status.aspx", headers=headers, data=data, timeout=HTTP_TIMEOUT)
            soup = BeautifulSoup(r.text, features="lxml")

            def text_of(suffix):
                el = soup.find("span", id=STATUS_PREFIX + suffix)
                return el.get_text(strip=True) if el else None

            status = text_of("lblStatus")
            if not status:
                # Missing status span == wrong captcha / validation error page -> retry.
                continue

            application_num_returned = text_of("lblCaseNo")
            if not application_num_returned or application_num_returned.strip() != application_num.strip():
                print(f"Case number mismatch (got {application_num_returned!r}); retrying.")
                continue

            case_last_updated = text_of("lblStatusDate")
            if not case_last_updated:
                print("Status date missing; retrying.")
                continue

            result.update({
                "success": True,
                "time": str(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())),
                "visa_type": text_of("lblAppName"),
                "status": status,
                "case_created": text_of("lblSubmitDate"),
                "case_last_updated": case_last_updated,
                "description": text_of("lblMessage"),
                "application_num": application_num_returned,
                "application_num_origin": application_num,
            })
            break

        except Exception as e:  # noqa: BLE001 - any per-attempt failure should just retry
            print(f"Attempt {failCount + 1} error: {e}")
            continue

    return result
