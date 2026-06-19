import datetime
import json
import os
import tempfile

from CEACStatusBot.captcha import CaptchaHandle, OnnxCaptchaHandle
from CEACStatusBot.request import query_status

from .handle import NotificationHandle


class NotificationManager:
    def __init__(
        self,
        location: str,
        number: str,
        passport_number: str,
        surname: str,
        captchaHandle: CaptchaHandle = OnnxCaptchaHandle("captcha.onnx"),
    ) -> None:
        self.__handleList = []
        self.__location = location
        self.__number = number
        self.__captchaHandle = captchaHandle
        self.__passport_number = passport_number
        self.__surname = surname
        self.__status_file = "status_record.json"

    def addHandle(self, notificationHandle: NotificationHandle) -> None:
        self.__handleList.append(notificationHandle)

    def send(self, force_send: bool = False) -> dict:
        """Query CEAC and notify.

        - Emails immediately when the status changed vs the last recorded status
          (change = EITHER the status text OR the last-updated date differs).
        - When ``force_send`` is True (nightly summary), emails regardless of change,
          and even on a query failure sends a heartbeat so a silent outage is visible.

        Crucially, the new status is persisted ONLY AFTER notifications succeed, so a
        transient email failure never swallows a change — the next run re-detects it.
        """
        res = query_status(
            self.__location,
            self.__number,
            self.__passport_number,
            self.__surname,
            self.__captchaHandle,
        )

        if not res.get("success"):
            if force_send:
                # Nightly summary must produce SOME email even when the query failed,
                # so "no email" can't be silently mistaken for "no change".
                self.__try_notify({
                    "success": False,
                    "application_num_origin": self.__number,
                    "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                })
            raise RuntimeError("Query status failed, no status retrieved.")

        current_status = res["status"]
        current_last_updated = res["case_last_updated"]
        print(f"Current status: {current_status} - Last updated: {current_last_updated}")

        statuses = self.__load_statuses()
        previous = statuses[-1] if statuses else None
        res["previous"] = previous

        changed = (
            previous is None
            or current_status != previous.get("status")
            or current_last_updated != previous.get("last_updated")
        )

        if changed or force_send:
            print(f"Sending notification ({'change detected' if changed else 'daily summary'}).")
            # Send first; if a handle raises, the exception propagates and we do NOT
            # advance the record, so the change is retried on the next run.
            self.__send_notifications(res)
            if changed:
                self.__save_current_status(current_status, current_last_updated)
        else:
            print("Status unchanged. No notification sent.")

        return res

    def __load_statuses(self) -> list:
        if not os.path.exists(self.__status_file):
            return []
        try:
            with open(self.__status_file, encoding="utf-8") as file:
                data = json.load(file)
        except (json.JSONDecodeError, OSError) as e:
            print(f"[state] status_record.json unreadable ({e}); treating history as empty.")
            return []
        return data.get("statuses", []) if isinstance(data, dict) else []

    def __save_current_status(self, status: str, last_updated: str) -> None:
        statuses = self.__load_statuses()
        statuses.append({
            "status": status,
            "last_updated": last_updated,
            "date": datetime.datetime.now().isoformat(),
        })
        # Atomic write: dump to a temp file in the same dir, then os.replace().
        directory = os.path.dirname(os.path.abspath(self.__status_file))
        fd, tmp = tempfile.mkstemp(dir=directory, prefix=".status_", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump({"statuses": statuses}, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.__status_file)
        except Exception:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise

    def __send_notifications(self, res: dict) -> None:
        for notificationHandle in self.__handleList:
            notificationHandle.send(res)

    def __try_notify(self, res: dict) -> None:
        """Best-effort notify that never raises (used for the failure heartbeat)."""
        for notificationHandle in self.__handleList:
            try:
                notificationHandle.send(res)
            except Exception as e:  # noqa: BLE001
                print(f"[notify] heartbeat send failed: {e}")
