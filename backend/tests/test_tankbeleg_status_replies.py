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
    # DLE EOT n=5 ist die Slip-Paper-Sensor-Abfrage (TM-U295) - kritisch fuer Sening
    out = reader._handle_status_queries(b"\x10\x04\x05")
    assert out == b"", "Status-Query darf nicht im Print-Buffer landen"
    assert bytes(reader.ser.written) == b"\x12", f"Slip-Paper-Status muss 0x12 antworten, war {reader.ser.written.hex()}"


def test_dle_eot_all_n_values_reply_0x12():
    """TM-U295 hat n=1, 2, 3, 5 - n=4 existiert NICHT (war TM-U220)."""
    reader = _make_reader()
    for n in (1, 2, 3, 5):
        reader.ser.written.clear()
        out = reader._handle_status_queries(bytes([0x10, 0x04, n]))
        assert out == b""
        assert bytes(reader.ser.written) == b"\x12", f"DLE EOT {n} sollte 0x12 antworten"


def test_dle_eot_n4_replies_0x12_safety_net():
    """TM-U295 Spec hat kein n=4 - aber Sening 3.56[3.57]DE schickt es eventuell
    aus altem TM-U220-Profil. Safety-Reply 0x12."""
    reader = _make_reader()
    out = reader._handle_status_queries(b"\x10\x04\x04")
    assert out == b"", "n=4 muss aus dem Buffer entfernt werden"
    assert bytes(reader.ser.written) == b"\x12", "n=4 Safety-Reply 0x12"


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
    """TM-U295 ESC u 0 ist 3 Bytes (drawer status)."""
    reader = _make_reader()
    out = reader._handle_status_queries(b"\x1b\x75\x00")
    assert out == b""
    assert bytes(reader.ser.written) == b"\x00"


def test_esc_c_3_silently_consumed():
    """ESC c 3 n (Paper-Sensor-Auswahl) muss aus dem Buffer raus, keine Antwort."""
    reader = _make_reader()
    out = reader._handle_status_queries(b"\x1b\x63\x33\x30HELLO")
    assert out == b"HELLO", "Druckdaten nach ESC c 3 muessen erhalten bleiben"
    assert reader.ser.written == b"", "ESC c 3 darf keine Antwort senden"


def test_esc_c_4_silently_consumed():
    """ESC c 4 n (Stop-on-Paper-End) muss aus dem Buffer raus, keine Antwort."""
    reader = _make_reader()
    out = reader._handle_status_queries(b"\x1b\x63\x34\x20WORLD")
    assert out == b"WORLD"
    assert reader.ser.written == b""


def test_esc_c_partial_buffered():
    """ESC c am Chunk-Ende mit < 4 Bytes muss vorgehalten werden."""
    reader = _make_reader()
    out1 = reader._handle_status_queries(b"data\x1b\x63\x33")
    assert out1 == b"data"
    assert reader.ser.written == b""
    out2 = reader._handle_status_queries(b"\x30more")
    assert out2 == b"more"
    assert reader.ser.written == b""


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
    payload = b"\x10\x04\x05" + b"PRINT" + b"\x10\x04\x01"
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
    # Zweites Chunk liefert das fehlende n=5 (TM-U295 slip paper status)
    out2 = reader._handle_status_queries(b"\x05MORE")
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


def test_script_version_is_178():
    mod = _load_module()
    assert mod.SCRIPT_VERSION == "1.7.8", f"SCRIPT_VERSION sollte 1.7.8 sein, ist {mod.SCRIPT_VERSION}"


def test_default_sening_reply_byte_is_0x00():
    """Empirisch validierter Default 0x00 fuer Sening 3.56[3.57]DE.
    0x12 wuerde TM-U295-Spec entsprechen, funktioniert hier aber NICHT
    weil ESC B3 nicht in der Spec ist (Sening-proprietaer)."""
    mod = _load_module()
    assert mod.DEFAULT_CONF["sening_reply_byte"] == "0x00"


def test_default_ftdi_latency_ms_is_1():
    mod = _load_module()
    assert mod.DEFAULT_CONF["ftdi_latency_ms"] == 1


if __name__ == "__main__":
    import subprocess
    sys.exit(subprocess.call(["pytest", "-xvs", __file__]))
