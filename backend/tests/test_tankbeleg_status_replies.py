"""Unit-Tests fuer die v1.7.5 Status-Reply-Erweiterungen im Tankbeleg-Pi.

Verifiziert dass:
  - DLE EOT n (1..4) -> 0x12 (Paper OK / online)
  - DLE ENQ n        -> 0x00
  - ESC v            -> 0x00 (paper present)
  - ESC u            -> 0x00 (peripheral ok)
  - GS r n           -> 0x00 (paper roll / drawer ok)
  - ESC B3 n         -> sening_reply_byte (default 0x00)
  - Status-Bytes werden aus dem Buffer ENTFERNT, damit sie nicht in den
    Beleg geschrieben werden.
  - Print-Daten (z.B. ESC J = feed) bleiben im Buffer.
"""
import os
import sys
import importlib.util


HERE = os.path.dirname(os.path.abspath(__file__))
TANKBELEG_PATH = os.path.normpath(os.path.join(HERE, "..", "static", "tankbeleg_pi.py"))


def _load_module():
    spec = importlib.util.spec_from_file_location("tankbeleg_pi", TANKBELEG_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["tankbeleg_pi"] = mod
    spec.loader.exec_module(mod)
    return mod


class FakeSerial:
    """Minimaler Stub, der ser.write() aufzeichnet."""
    def __init__(self):
        self.written = bytearray()

    def write(self, data):
        self.written.extend(data)

    def flush(self):
        pass


def _make_reader():
    mod = _load_module()
    reader = mod.SerialReceiptReader.__new__(mod.SerialReceiptReader)
    reader.ser = FakeSerial()
    reader.sening_reply_byte = 0x00
    reader.pending_prefix = bytearray()
    reader.raw_stream = None
    return reader


def test_dle_eot_paper_status_replies_0x12():
    reader = _make_reader()
    # DLE EOT n=4 ist die Paper-Sensor-Abfrage - kritisch fuer Sening
    out = reader._handle_status_queries(b"\x10\x04\x04")
    assert out == b"", "Status-Query darf nicht im Print-Buffer landen"
    assert bytes(reader.ser.written) == b"\x12", f"Paper-Status muss 0x12 antworten, war {reader.ser.written.hex()}"


def test_dle_eot_all_n_values_reply_0x12():
    reader = _make_reader()
    for n in (1, 2, 3, 4):
        reader.ser.written.clear()
        out = reader._handle_status_queries(bytes([0x10, 0x04, n]))
        assert out == b""
        assert bytes(reader.ser.written) == b"\x12", f"DLE EOT {n} sollte 0x12 antworten"


def test_dle_enq_replies_0x00():
    reader = _make_reader()
    out = reader._handle_status_queries(b"\x10\x05\x01")
    assert out == b""
    assert bytes(reader.ser.written) == b"\x00"


def test_esc_v_paper_sensor_replies_0x00():
    """TM-U295 legacy paper sensor query - 0x00 = paper present, not near-end."""
    reader = _make_reader()
    out = reader._handle_status_queries(b"\x1b\x76")
    assert out == b""
    assert bytes(reader.ser.written) == b"\x00"


def test_esc_u_peripheral_status_replies_0x00():
    reader = _make_reader()
    out = reader._handle_status_queries(b"\x1b\x75")
    assert out == b""
    assert bytes(reader.ser.written) == b"\x00"


def test_gs_r_paper_roll_replies_0x00():
    reader = _make_reader()
    out = reader._handle_status_queries(b"\x1d\x72\x01")
    assert out == b""
    assert bytes(reader.ser.written) == b"\x00"


def test_gs_r_drawer_replies_0x00():
    reader = _make_reader()
    out = reader._handle_status_queries(b"\x1d\x72\x02")
    assert out == b""
    assert bytes(reader.ser.written) == b"\x00"


def test_sening_poll_uses_configured_reply_byte():
    reader = _make_reader()
    reader.sening_reply_byte = 0x12
    out = reader._handle_status_queries(b"\x1b\xb3\xff")
    assert out == b""
    assert bytes(reader.ser.written) == b"\x12"


def test_print_data_passes_through():
    """Echte Print-Bytes (z.B. ESC J = line feed) duerfen NICHT verschluckt werden."""
    reader = _make_reader()
    # ESC J 0x10 = "feed paper 16/180 inch" - darf NICHT als Status-Query
    # missinterpretiert werden, weil ESC J nicht in unserer Status-Liste ist.
    out = reader._handle_status_queries(b"\x1b\x4a\x10Hello")
    assert b"Hello" in out, "Druckdaten muessen erhalten bleiben"
    assert reader.ser.written == b"", "Auf ESC J darf nichts geantwortet werden"


def test_mixed_status_and_print_data():
    """Status-Query gefolgt von Print-Daten gefolgt von noch einer Status-Query."""
    reader = _make_reader()
    payload = b"\x10\x04\x04" + b"PRINT" + b"\x10\x04\x01"
    out = reader._handle_status_queries(payload)
    assert out == b"PRINT"
    assert bytes(reader.ser.written) == b"\x12\x12"


def test_partial_status_query_buffered_across_reads():
    """Wenn ein Chunk an einer halben Status-Sequenz endet, darf das nicht im
    Buffer landen, sondern muss bis zum naechsten read() vorgehalten werden."""
    reader = _make_reader()
    # Erstes Chunk endet mit 0x10 0x04 (incomplete - n fehlt)
    out1 = reader._handle_status_queries(b"DATA\x10\x04")
    assert out1 == b"DATA"
    assert reader.ser.written == b"", "Noch keine Antwort - Sequenz unvollstaendig"
    # Zweites Chunk liefert das fehlende n=4
    out2 = reader._handle_status_queries(b"\x04MORE")
    assert out2 == b"MORE"
    assert bytes(reader.ser.written) == b"\x12"


def test_partial_esc_v_buffered():
    """ESC ohne folgendes Byte am Chunk-Ende darf nicht durchschlupfen."""
    reader = _make_reader()
    out1 = reader._handle_status_queries(b"hi\x1b")
    assert out1 == b"hi"
    out2 = reader._handle_status_queries(b"\x76rest")
    assert out2 == b"rest"
    assert bytes(reader.ser.written) == b"\x00"


def test_script_version_is_177():
    mod = _load_module()
    assert mod.SCRIPT_VERSION == "1.7.7", f"SCRIPT_VERSION sollte 1.7.7 sein, ist {mod.SCRIPT_VERSION}"


def test_default_ftdi_latency_ms_is_1():
    mod = _load_module()
    assert mod.DEFAULT_CONF["ftdi_latency_ms"] == 1


if __name__ == "__main__":
    import subprocess
    sys.exit(subprocess.call(["pytest", "-xvs", __file__]))
