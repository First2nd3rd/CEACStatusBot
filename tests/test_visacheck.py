"""Unit tests for visacheck change-detection, persistence ordering, and formatting.

Run from the repo root:  ./.venv/bin/python -m pytest -q
"""

import json

import pytest

from CEACStatusBot.notification import manager as mgr_mod
from CEACStatusBot.notification.manager import NotificationManager
from CEACStatusBot.notification.format import build_body, build_subject


def _result(status="Refused", last_updated="15-Jun-2026", previous="__absent__"):
    r = {
        "success": True,
        "status": status,
        "case_last_updated": last_updated,
        "case_created": "11-Jun-2026",
        "visa_type": "NONIMMIGRANT VISA APPLICATION",
        "description": "consular message",
        "application_num": "AA00FIV5AH",
        "application_num_origin": "AA00FIV5AH",
        "time": "2026-06-19 12:00:00",
    }
    if previous != "__absent__":
        r["previous"] = previous
    return r


class RecordingHandle:
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = []

    def send(self, res):
        self.calls.append(res)
        if self.fail:
            raise RuntimeError("smtp down")


def _mgr(monkeypatch, query_result, handle):
    monkeypatch.setattr(mgr_mod, "query_status", lambda *a, **k: query_result)
    m = NotificationManager("CHINA, BEIJING", "AA00FIV5AH", "EE5022685", "FANG")
    m.addHandle(handle)
    return m


def _seed(tmp_path, status="Refused", last_updated="15-Jun-2026"):
    (tmp_path / "status_record.json").write_text(
        json.dumps({"statuses": [{"status": status, "last_updated": last_updated, "date": "seed"}]})
    )


# ---- formatting ----

def test_subject_first_record():
    assert "首次记录" in build_subject(_result(previous=None))


def test_subject_unchanged():
    assert "无变化" in build_subject(_result(previous={"status": "Refused", "last_updated": "15-Jun-2026"}))


def test_status_change_rendered():
    r = _result(status="Issued", previous={"status": "Refused", "last_updated": "15-Jun-2026"})
    assert "状态有变化" in build_subject(r)
    assert "Refused → Issued" in build_body(r)


def test_date_only_change_counts():
    r = _result(last_updated="20-Jun-2026", previous={"status": "Refused", "last_updated": "15-Jun-2026"})
    assert "状态有变化" in build_subject(r)
    assert "15-Jun-2026 → 20-Jun-2026" in build_body(r)


def test_failure_render():
    assert "查询失败" in build_subject({"success": False, "application_num_origin": "AA00FIV5AH"})
    assert "查询失败" in build_body({"success": False, "application_num_origin": "AA00FIV5AH"})


# ---- manager: ordering / persistence / change detection ----

def test_change_not_persisted_when_send_fails(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    h = RecordingHandle(fail=True)
    m = _mgr(monkeypatch, _result(status="Issued", last_updated="20-Jun-2026"), h)
    with pytest.raises(RuntimeError):
        m.send()
    assert len(h.calls) == 1                                  # attempted to send
    assert not (tmp_path / "status_record.json").exists()     # but did NOT persist


def test_change_persisted_on_success(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    h = RecordingHandle()
    m = _mgr(monkeypatch, _result(status="Issued", last_updated="20-Jun-2026"), h)
    m.send()
    data = json.loads((tmp_path / "status_record.json").read_text())
    assert data["statuses"][-1]["status"] == "Issued"


def test_unchanged_sends_nothing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed(tmp_path)
    h = RecordingHandle()
    m = _mgr(monkeypatch, _result(status="Refused", last_updated="15-Jun-2026"), h)
    m.send()
    assert h.calls == []


def test_summary_sends_even_when_unchanged_without_appending(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _seed(tmp_path)
    h = RecordingHandle()
    m = _mgr(monkeypatch, _result(status="Refused", last_updated="15-Jun-2026"), h)
    m.send(force_send=True)
    assert len(h.calls) == 1
    data = json.loads((tmp_path / "status_record.json").read_text())
    assert len(data["statuses"]) == 1                         # unchanged -> not appended


def test_corrupt_record_is_tolerated(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "status_record.json").write_text("{ broken json")
    h = RecordingHandle()
    m = _mgr(monkeypatch, _result(status="Refused", last_updated="15-Jun-2026"), h)
    m.send()                                                  # treats history as empty -> sends + persists
    assert len(h.calls) == 1
    data = json.loads((tmp_path / "status_record.json").read_text())
    assert data["statuses"][-1]["status"] == "Refused"


def test_failure_heartbeat_only_on_summary(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    h = RecordingHandle()
    m = _mgr(monkeypatch, {"success": False}, h)
    with pytest.raises(RuntimeError):
        m.send(force_send=True)
    assert len(h.calls) == 1 and h.calls[0].get("success") is False


def test_no_heartbeat_on_poll_failure(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    h = RecordingHandle()
    m = _mgr(monkeypatch, {"success": False}, h)
    with pytest.raises(RuntimeError):
        m.send(force_send=False)
    assert h.calls == []
