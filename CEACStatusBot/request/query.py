import random
import time

import requests
from bs4 import BeautifulSoup

from CEACStatusBot.captcha import CaptchaHandle, OnnxCaptchaHandle

# (connect timeout, read timeout) for every HTTP call so a hung connection can
# never wedge the scheduled job forever.
HTTP_TIMEOUT = (10, 30)

MAX_ATTEMPTS = 5

CAPTCHA_IMG_ID = "c_status_ctl00_contentplaceholder1_defaultcaptcha_CaptchaImage"
STATUS_PREFIX = "ctl00_ContentPlaceHolder1_ucApplicationStatusView_"

# Stable failure-reason keys. query/manager render these to English for the log;
# format.py renders the same keys to the user's language for the email.
REASON_TEXT = {
    "wrong_captcha": "likely wrong captcha (form returned without a status)",
    "blocked": "blocked/forbidden (HTTP 403) — possible IP or proxy block",
    "rate_limited": "rate-limited (HTTP 429) — possible block from too many requests",
    "server_error": "CEAC server error or maintenance (HTTP 5xx)",
    "http_error": "unexpected HTTP response from CEAC",
    "empty_page": "unexpected short/empty page — possible block or outage",
    "no_status": "no status on the page — likely wrong captcha or a CEAC-side change",
    "captcha_missing": "captcha image missing — possible block or CEAC-side change",
    "location_missing": "location dropdown missing — possible block or CEAC-side change",
    "case_mismatch": "returned case number did not match",
    "date_missing": "status found but date missing — likely a CEAC-side change",
    "network_timeout": "network timeout — CEAC slow or your connection/proxy",
    "connection_failed": "connection failed — network/proxy/DNS issue (not necessarily a block)",
    "config": "configuration problem",
    "unknown": "unexpected error",
}


def _classify_no_status(resp) -> str:
    """Best-effort reason key for a request that came back without a status, so
    the log can tell a wrong captcha apart from a block or a CEAC-side outage."""
    code = resp.status_code
    if code == 403:
        return "blocked"
    if code == 429:
        return "rate_limited"
    if code in (500, 502, 503, 504):
        return "server_error"
    if code != 200:
        return "http_error"
    body = (resp.text or "").lower()
    if "defaultcaptcha" in body or "captcha" in body:
        return "wrong_captcha"
    if len(body) < 500:
        return "empty_page"
    return "no_status"


def _dominant_reason(reasons: list[str]) -> str:
    """The reason key seen most often across attempts (for the final summary)."""
    if not reasons:
        return "unknown"
    return max(set(reasons), key=reasons.count)


def query_status(location, application_num, passport_number, surname, captchaHandle: CaptchaHandle = OnnxCaptchaHandle("captcha.onnx")):
    result = {"success": False}
    reasons: list[str] = []

    def note(reason_key: str, detail: str = "") -> None:
        msg = REASON_TEXT.get(reason_key, reason_key)
        print(f"Attempt {failCount + 1}: {msg}{f' ({detail})' if detail else ''}")
        reasons.append(reason_key)

    for failCount in range(MAX_ATTEMPTS):
        if failCount > 0:
            # Randomised back-off so retries don't look like clockwork.
            backupTime = random.uniform(4, 9)
            print(f"Retrying... Attempt {failCount + 1} / {MAX_ATTEMPTS} in {backupTime:.1f}s")
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
                note(_classify_no_status(r) if r.status_code != 200 else "captcha_missing")
                continue
            img_resp = session.get(ROOT + captcha["src"], timeout=HTTP_TIMEOUT)
            captcha_num = captchaHandle.solve(img_resp.content)
            print(f"Captcha solved: {captcha_num}")

            # Location dropdown -> the option value whose visible text contains `location`
            location_dropdown = soup.find("select", id="Location_Dropdown")
            if location_dropdown is None:
                note("location_missing")
                continue
            location_value = None
            for option in location_dropdown.find_all("option"):
                if location in option.get_text():
                    location_value = option.get("value")
                    break
            if not location_value:
                # Configuration problem, not a transient one — no point retrying.
                return {
                    "success": False,
                    "reason_key": "config",
                    "reason": f"location '{location}' not found in the dropdown — check your LOCATION setting",
                }

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
                # No status span -> classify why (wrong captcha vs block vs outage).
                note(_classify_no_status(r))
                continue

            application_num_returned = text_of("lblCaseNo")
            if not application_num_returned or application_num_returned.strip() != application_num.strip():
                note("case_mismatch", f"got {application_num_returned!r}")
                continue

            case_last_updated = text_of("lblStatusDate")
            if not case_last_updated:
                note("date_missing")
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

        except requests.exceptions.Timeout:
            note("network_timeout")
            continue
        except requests.exceptions.ConnectionError:
            note("connection_failed")
            continue
        except Exception as e:  # noqa: BLE001 - any other per-attempt failure should just retry
            note("unknown", str(e))
            continue

    if not result.get("success"):
        key = _dominant_reason(reasons)
        result["reason_key"] = key
        result["reason"] = f"{REASON_TEXT.get(key, key)} ({reasons.count(key)}/{len(reasons)} attempts)"
    return result
