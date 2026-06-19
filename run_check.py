"""Local entry point for the CEAC visa-status checker.

    python run_check.py            # poll: send an email ONLY if the status changed
    python run_check.py --summary  # always send an email (used by the nightly job)
    python run_check.py --print    # also print the full report to stdout (manual use)
    python run_check.py --jitter 1200   # sleep random 0..1200s first (used by launchd)

Flags combine, e.g. `python run_check.py --summary --print` for a manual check
that always emails and shows the result.

Reads config from .env in this directory. Run from the repo root so the bundled
captcha.onnx and .env are found (launchd sets WorkingDirectory for this).
"""

import argparse
import os
import random
import time

from dotenv import load_dotenv

from CEACStatusBot import EmailNotificationHandle, NotificationManager
from CEACStatusBot.notification.format import build_body


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Check CEAC NIV visa status and notify.")
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Force-send an email even when the status is unchanged (nightly summary).",
    )
    parser.add_argument(
        "--print",
        dest="do_print",
        action="store_true",
        help="Print the full status report to stdout.",
    )
    parser.add_argument(
        "--jitter",
        type=int,
        default=0,
        metavar="SECONDS",
        help="Sleep a random 0..SECONDS before querying, so scheduled runs don't hit CEAC on an exact clock tick.",
    )
    args = parser.parse_args()

    if args.jitter > 0:
        delay = random.randint(0, args.jitter)
        print(f"Jitter: sleeping {delay}s before querying...")
        time.sleep(delay)

    try:
        location = os.environ["LOCATION"]
        number = os.environ["NUMBER"]
        passport_number = os.environ["PASSPORT_NUMBER"]
        surname = os.environ["SURNAME"]
    except KeyError as e:
        raise SystemExit(f"Missing required config in .env: {e}")

    manager = NotificationManager(location, number, passport_number, surname)

    from_email = os.getenv("FROM")
    to_email = os.getenv("TO")
    password = os.getenv("PASSWORD")
    smtp = os.getenv("SMTP", "")
    if from_email and to_email and password:
        manager.addHandle(EmailNotificationHandle(from_email, to_email, password, smtp))
    else:
        print("Email not configured (FROM/TO/PASSWORD); will only log to console.")

    res = manager.send(force_send=args.summary)

    if args.do_print:
        print()
        print(build_body(res))


if __name__ == "__main__":
    main()
