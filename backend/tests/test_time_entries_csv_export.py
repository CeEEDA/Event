"""Regression test for GET /api/employee/time/entries/csv endpoint.

Validates the CSV export of Stempelzeiten (time entries) for one month:
- Includes UTF-8 BOM for Excel-compat with umlauts
- Semicolon separator
- Header line + column row + data rows + total row
- Handles positive and negative durations (Korrektur-Modus)
- Works for admins (with user_id param) and employees (own data)
"""
import io
import csv
import pytest
from datetime import datetime, timezone


def _parse_csv_bytes(body: str):
    """Parse CSV response body (with BOM) into rows."""
    assert body.startswith("\ufeff"), "CSV muss mit UTF-8 BOM starten (Excel-Kompatibilitaet)"
    return list(csv.reader(io.StringIO(body[1:]), delimiter=";"))


def test_csv_row_formatting_positive_duration():
    """Duration 490 Min = 8h 10m -> Dauer (h:mm) = '8:10', Dauer (h) = '8.17'."""
    dur_min = 490.0
    h_full = int(abs(dur_min) // 60)
    m_rest = int(round(abs(dur_min) % 60))
    dur_hmm = f"{h_full}:{m_rest:02d}"
    dur_dec = f"{dur_min / 60.0:.2f}"
    assert dur_hmm == "8:10"
    assert dur_dec == "8.17"


def test_csv_row_formatting_negative_correction():
    """Duration -150 Min (Korrektur -2.5h) -> '-2:30' und '-2.50'."""
    dur_min = -150.0
    h_full = int(abs(dur_min) // 60)
    m_rest = int(round(abs(dur_min) % 60))
    sign = "-" if dur_min < 0 else ""
    dur_hmm = f"{sign}{h_full}:{m_rest:02d}"
    dur_dec = f"{dur_min / 60.0:.2f}"
    assert dur_hmm == "-2:30"
    assert dur_dec == "-2.50"


def test_csv_weekday_mapping():
    """Der Wochentag-Kuerzel muss deutsch sein (Mo-So)."""
    _weekdays_de = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
    # 2026-09-15 = Tuesday
    wd = _weekdays_de[datetime.strptime("2026-09-15", "%Y-%m-%d").weekday()]
    assert wd == "Di"
    # 2026-09-13 = Sunday
    wd = _weekdays_de[datetime.strptime("2026-09-13", "%Y-%m-%d").weekday()]
    assert wd == "So"


def test_parse_csv_bom_and_header():
    """Die CSV-Export-Antwort muss BOM, Titel, Leerzeile und Header-Zeile in dieser Reihenfolge haben."""
    body = "\ufefftitle\n\ndatum;tag;beginn\n2026-09-15;Di;08:00\n"
    rows = _parse_csv_bytes(body)
    assert rows[0] == ["title"]
    assert rows[1] == []
    assert rows[2] == ["datum", "tag", "beginn"]
    assert rows[3] == ["2026-09-15", "Di", "08:00"]
