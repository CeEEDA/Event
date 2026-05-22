"""Regression test for OTA self-update helpers in dse_usb_sync.py."""
import importlib.util
import os
import sys
import types


def _load_dse_module():
    path = os.path.abspath(os.path.join(
        os.path.dirname(__file__), "..", "static", "dse_usb_sync.py"
    ))
    spec = importlib.util.spec_from_file_location("dse_usb_sync", path)
    mod = importlib.util.module_from_spec(spec)
    if "usb" not in sys.modules:
        usb = types.ModuleType("usb")
        usb.core = types.ModuleType("usb.core")
        usb.util = types.ModuleType("usb.util")
        usb.core.USBError = Exception
        sys.modules["usb"] = usb
        sys.modules["usb.core"] = usb.core
        sys.modules["usb.util"] = usb.util
    spec.loader.exec_module(mod)
    return mod


def test_parse_remote_version():
    mod = _load_dse_module()
    assert mod._parse_remote_version('SCRIPT_VERSION = "2.1.0"\n') == "2.1.0"
    assert mod._parse_remote_version("SCRIPT_VERSION = '3.14.159'") == "3.14.159"
    assert mod._parse_remote_version("# no version line here") == ""
    assert mod._parse_remote_version("") == ""


def test_version_tuple_ordering():
    mod = _load_dse_module()
    assert mod._version_tuple("2.1.0") > mod._version_tuple("2.0.3")
    assert mod._version_tuple("2.1.10") > mod._version_tuple("2.1.9")
    assert mod._version_tuple("2.0.0") < mod._version_tuple("10.0.0")
    assert mod._version_tuple("garbage") == (0, 0, 0)
    # Equal versions should NOT trigger update
    assert not (mod._version_tuple("2.1.0") > mod._version_tuple("2.1.0"))


def test_ota_skips_when_same_or_older(monkeypatch):
    """OTA darf weder bei gleicher noch bei aelterer Version self-replace ausloesen."""
    mod = _load_dse_module()
    replaced = {"called": False}

    def fake_get(*args, **kwargs):
        class R:
            status_code = 200
            text = f'SCRIPT_VERSION = "{mod.SCRIPT_VERSION}"\nprint("hi")\n'
        return R()

    def fake_replace(*args, **kwargs):
        replaced["called"] = True

    monkeypatch.setattr(mod.requests, "get", fake_get)
    monkeypatch.setattr(mod.os, "replace", fake_replace)
    mod.ota_check_and_apply("https://example.com/api")
    assert replaced["called"] is False
