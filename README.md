# visacheck — local CEAC visa-status monitor

A small **local macOS** tool that checks a US **nonimmigrant visa (NIV)** application
status on [CEAC](https://ceac.state.gov/CEACStatTracker/Status.aspx) on a schedule
and emails you. Forked from
[Andision/CEACStatusBot](https://github.com/Andision/CEACStatusBot) and adapted to
run entirely locally (no cloud, no paid captcha service).

> 中文说明见 [README.Chinese.md](README.Chinese.md)。

## Why local-only

CEAC sits behind an anti-bot WAF that blocks datacenter IPs, so this is designed to
run from your own machine on your residential IP. Do **not** run it from CI / GitHub
Actions. The captcha is solved offline by the bundled `captcha.onnx` model (free).

## Setup

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -U pip beautifulsoup4 lxml numpy onnxruntime pillow python-dotenv requests
cp .env.example .env      # then fill in the values below
```

`.env` (gitignored — never commit it):

| key | meaning |
|-----|---------|
| `LOCATION` | consular post text, e.g. `CHINA, BEIJING` (see `LOCATION.md`) |
| `NUMBER` | DS-160 application id (`AA...`) |
| `PASSPORT_NUMBER` | passport number |
| `SURNAME` | first 5 letters of surname |
| `FROM` / `TO` | sender / recipient email (same Gmail = self-send) |
| `PASSWORD` | Gmail **App Password** (not your login password) |
| `SMTP` | `smtp.gmail.com:465` |

## Usage

```bash
./.venv/bin/python run_check.py              # poll: email only if status changed
./.venv/bin/python run_check.py --summary    # always email (nightly summary)
./.venv/bin/python run_check.py --print      # also print the report to stdout
```

Change detection compares `(status, last_updated)` to the last entry in
`status_record.json`; either differing counts as a change. The new status is
persisted only after the email is sent, so a transient send failure is retried.

## Scheduling (launchd)

```bash
bash scheduling/install.sh     # poll 00/03/09/12/15/18 + nightly summary 21:00
bash scheduling/uninstall.sh   # stop all scheduled checks
```

Runs while you are logged in; survives reboot; does not wake the Mac but runs a
catch-up on wake. Logs: `logs/visacheck.log`.

## Tests

```bash
./.venv/bin/python -m pip install pytest
./.venv/bin/python -m pytest -q
```
