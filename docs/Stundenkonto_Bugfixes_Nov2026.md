# Stundenkonto – Bugfixes (Nov 2026)

Übergabe an einen Agenten, der die Fixes im Quellcode umsetzt bzw. übernimmt.

- **Projekt:** Eventenergie-Portal, FastAPI-Backend + React-Frontend, MongoDB `eventenergie`
- **Basis-Commit:** `dd19c20`
- **Fertiger Patch (alle Änderungen + Tests):** `Stundenkonto_Fix_Nov2026.patch` (liegt neben dieser Datei)
  → bevorzugt: `git apply Stundenkonto_Fix_Nov2026.patch` im Repo-Root. Diese Beschreibung erklärt, *was* und *warum*, falls der Patch nicht sauber passt.
- **Betroffene Dateien:**
  - `backend/routes/employee.py` (Hauptteil)
  - `backend/routes/offdays.py`
  - `backend/routes/chat.py`
  - `frontend/src/pages/EinsatzplanungPage.jsx`
  - `frontend/src/components/admin/zeit_detail/AuditLogSection.jsx`
  - neu: `backend/tests/test_stundenkonto_bugs_nov2026.py`

---

## Grundprinzip des Stundenkontos (zum Verständnis)

`_recompute_overtime_for_year(user_id, year)` in `employee.py` berechnet den Saldo immer komplett neu:

```
overtime_hours = overtime_baseline + Tagesbilanz(Σ Ist − Soll je Tag ab range_start bis heute) − Abzüge
```

- `range_start` = Tag nach dem letzten **manuellen Setzen** des Kontos (`overtime_baseline_reason` beginnt mit `admin-manuell`, Zeitpunkt `overtime_baseline_set_at`). Alles davor steckt im manuell gesetzten Wert.
- Tage ohne Stempel an einem Plan-Arbeitstag zählen automatisch **−Soll**.
- **Regel, die alle Bugs verursacht hat:** Jeder Code, der `overtime_hours` **direkt** schreibt, wird beim nächsten Recompute überschrieben. Und alles, was zusätzlich auf `overtime_baseline` gebucht wird, darf in der Tagesbilanz **nicht nochmal** zählen.

---

## Bug 1 – Abgebaute Überstunden kommen zurück (P0)

**Symptom:** Bei Andre, Martin, Dirk, Christine (und Timo, Volker, Roberto, Ornela, Byron) wurden bereits abgebaute Überstunden ohne Erklärung wieder gutgeschrieben.
Beleg im Audit-Log: Martin 123,36h → 203,51h und Dirk 104,10h → 120,16h jeweils beim ersten `auto_balance_recompute` nach dem Abbau.

**Ursache:** Überstundenabbau (`time_off_requests`, `type="ueberstundenabbau"`) wurde nur per `$set overtime_hours = current − X` verbucht, an drei Stellen:
- `admin_create_time_off` (`POST /time-off/admin-create`) – zusätzlich **ohne `year`-Filter** auf `hr_data`
- `resolve_time_off_request` (`PUT /time-off/{id}`, status approved)
- `chat.py` → Task-Update: Antrag-Genehmigung über Aufgabe abschließen

Der Recompute liest Abzüge nur aus der Collection `absences` – die ist **leer** (keine Schreiber im Code). Abbau-Tage wurden im Recompute nur neutral gestellt (Soll 0), aber nie abgezogen. Nächster Recompute überschreibt → Stunden „zurück“.
Ebenso hat `admin_delete_time_off` beim Löschen direkt `+X` auf `overtime_hours` gebucht.

**Fix:**
1. Recompute verbucht Abbau selbst aus `time_off_requests` (approved, ueberstundenabbau):
   - Stunden pro Tag: `hours_deducted` (Stundenmodus) → sonst Uhrzeit-Spanne (`all_day=False`, `start_time/end_time`) → sonst ganzer Tag = Tages-Soll aus Wochenplan (nur Mo–Fr, wie bisherige Anzeige `hours_deducted_display`).
   - Pro Abbau-Tag: `soll_eff = max(0, Soll − abbau_h)`, Abzug `+= abbau_h`. Ganztags ⇒ Soll 0, Abzug = Soll. Stundenweise (z. B. 4,5h) ⇒ Rest-Soll bleibt.
   - **Zukünftige** Abbau-Tage werden sofort abgezogen (Konto zeigt geplanten Abbau).
   - Abbau-Tage **vor `range_start`** zählen nicht (gelten als im manuell gesetzten Wert enthalten) – auch wenn der Antrag erst danach erfasst wurde.
   - Feiertag / Urlaub / Krank haben Vorrang (kein Abzug).
2. Alle direkten `overtime_hours`-Schreibzugriffe für Abbau entfernt (`admin_create_time_off`, `resolve_time_off_request`, `admin_delete_time_off`, `chat.py`). Stattdessen: `await _recompute_and_describe(user_id, start, end)` (neuer Helper, Recompute mit `force=True` für alle betroffenen Jahre, liefert „2026: X h → Y h“) + Audit-Eintrag mit Stundenangabe.
3. `resolve_time_off_request` schreibt neuen Audit-Typ `time_off_resolve` (genehmigt/abgelehnt/zurückgezogen) und rechnet neu, wenn der Antrag vorher oder jetzt genehmigt ist (betrifft auch Urlaub/Krank).
4. Löschen eines Abbaus: Text „Abbau von X h storniert (vergangene Tage zählen wieder als normale Arbeitstage)“ – vergangene Tage ohne Stempel werden danach wieder −Soll, das ist korrekt.

---

## Bug 2 – Urlaub kostet trotzdem Stunden (P0)

**Symptom:** Mitarbeiter mit Urlaub bekommen Stunden abgezogen. Beleg: Byron 19 Urlaubstage (28.09.–23.10.) je −9h; Marcel 18.09. −9h.

**Ursache:** Der Recompute kennt nur `time_off_requests`. Direkt vom Admin eingetragener Urlaub liegt in **`vacation_entries`** (ohne Antrag, `POST /vacation/{user_id}`) und wurde ignoriert → Tag zählt als „Kein Stempel“ = −Soll.
Gleiches Loch in der Offday-Prüfung von Bug A (`offdays.py /adjust`) – prüfte nur `time_off_requests` Urlaub/Krank.

**Fix:**
- Recompute: `vacation_entries` des Users (Zeitraum überschneidet das Jahr) zu `off_days` hinzufügen (neutral, Soll 0).
- Neuer gemeinsamer Helper `offday_overtime_skip_reason(user_id, date)` in `employee.py`: Rückgabe `"Urlaub" | "Krank" | "Überstundenabbau" | "gestempelt" | None`. Prüft `time_off_requests` (approved: urlaub/krank/ueberstundenabbau), **`vacation_entries`** und echte `time_entries` (Typ nicht urlaub/krank/ueberstundenabbau/feiertag/korrektur, `duration_minutes > 0`).
- `offdays.py manual_adjust` nutzt diesen Helper statt eigener Abfragen.

---

## Bug 3 – Ein Offday wird doppelt abgezogen (P0)

**Symptom:** Martin bekam für einen einzigen Offday (18.09.) zweimal 9h abgezogen. Auch Andre (18.09.), Philipp (18.09. und 23.10.).

**Ursache:** Offdays buchen ihren Abzug **direkt auf `overtime_baseline`** (−Tages-Soll). Zusätzlich zählte die Tagesbilanz denselben Tag:
- Offday über **Offday-Konto** (`POST /api/employee/offdays/adjust`, delta < 0, mit `ref_date`): der Recompute kennt diese Offdays gar nicht → Tag ohne Stempel = −Soll. ⇒ doppelt.
- Offday über **Einsatzplan** (`shift_assignments.is_offday=True`): Recompute-Zweig „Offday (Ausgleichstag)“ setzte explizit `soll = Tages-Soll` → −Soll. ⇒ doppelt.
- Einsatzplan-Offday prüfte außerdem **nicht** auf Urlaub/Stempel (Bug A war nur in `/adjust` gefixt).

**Fix (Modell: Baseline-Buchung ist der EINE Abzug, Tag ist neutral):**
1. Recompute sammelt `prebooked_offdays` und stellt diese Tage neutral (Soll 0, Ist zählt):
   - aus `shift_assignments` (is_offday) – außer `overtime_deducted_h == 0` (kein Abzug gebucht → normaler Tag).
   - aus `time_audit_log` (`action="offday_manual_adjust"`, `after.overtime_delta_h < 0`, `after.ref_date` im Jahr).
   - jeweils nur, wenn **nach** `overtime_baseline_set_at` gebucht (sonst ist der Abzug im manuell gesetzten Wert nicht mehr drin → Tag zählt normal).
   - Reihenfolge der Tagesklassifizierung: Feiertag → Urlaub/Krank → Abbau → Offday → Nachtschicht-Folgetag → normal.
2. `offdays.py manual_adjust`: Audit-Eintrag **vor** dem Recompute schreiben (der Recompute liest ihn).
3. Einsatzplan (`upsert_shift_assignment`, alle drei Pfade: Mehrtages-Anlage, Einzel-Anlage, Offday↔Einsatz-Umwandlung) über neuen Helper `_offday_book_overtime(user_id, date, assignment_id)`:
   - Skip-Prüfung via `offday_overtime_skip_reason` → bei Urlaub/Krank/Abbau/gestempelt **kein** Abzug.
   - Sonst `$inc overtime_baseline: −Soll`.
   - Speichert am Assignment `overtime_deducted_h` (0 bei Skip) und `overtime_skip_reason`.
4. Löschen/Umwandeln (`delete_shift_assignment`, Flip Offday→Einsatz) über `_offday_refund_overtime(prev)`:
   - bucht **genau** `overtime_deducted_h` zurück (Alt-Einträge ohne Feld: Tages-Soll),
   - aber **nicht**, wenn das Assignment vor dem letzten manuellen Setzen angelegt wurde (sonst „geschenkte“ Stunden – genau das passierte am 17.09. bei Martin/Dirk: jedes gelöschte Offday +9h).
5. Audit-Texte nennen Abzug, Skip-Grund und Kontostand vorher→nachher.

---

## Bug 4 – Einsatzplan synchronisiert nicht mit Urlaub/anderen Einträgen (P1)

**Ursache:**
- `GET /employee/shift-plan` liefert Abwesenheiten aus `time_off_requests` + `vacation_entries`, aber **nicht** die Offdays aus dem Offday-Konto (`offday_ledger`) – über das in der Praxis **alle** Offdays gebucht werden (aktuell 0 Einsatzplan-Offdays in 2026).
- `EinsatzplanungPage.jsx` lud Daten nur beim Wochenwechsel; Änderungen aus anderen Bereichen erschienen erst nach F5.

**Fix:**
- Backend `get_shift_plan`: Aggregation über `offday_ledger` (`kind="manual_adjust"`, `ref_date` in der Woche), Summe `delta` je (user, Tag); wenn netto < 0 → Abwesenheit `{type:"offday", type_label:"Offday", source:"offday_ledger", start_date=end_date=ref_date}`. Tage mit Einsatzplan-Offday werden übersprungen (keine Doppelanzeige).
- Frontend `absenceLabel`: `offday` → „Offday (Konto)“, violett, Icon `CalendarCheck2`.
- Frontend: `useEffect` mit Reload (`loadPlan`, `loadOffdayBalances`) bei `window focus`, `visibilitychange` und alle 60 s.

---

## Transparenz – Änderungsprotokoll (P1)

**Problem:** Das System zeigte nicht klar, wann es selbst Stunden hinzufügt/abzieht:
- `auto_balance_day` wurde nur für **Minus**-Tage und nur **beim ersten Mal** geloggt. Spätere Änderungen eines Tages (Krankmeldung nachgetragen, Stempel korrigiert) und alle Plus-Tage waren unsichtbar.
- `auto_balance_recompute` zeigte kumulierte Jahreswerte („+35h an 8 Tagen …“), nicht was sich **jetzt** geändert hat.
- Label „Kein Stempel“ auch bei Tagen mit Ist > 0.
- UI schnitt die Texte ab (`truncate`) und unterschied System vs. manuell nicht.

**Fix Backend (Recompute, Schritte 8/9):**
- `day_effects[date] = {soll_min, ist_min, abbau_min, effect_min = (ist − soll_eff) − abbau, reason}`.
- Pro Tag Log, wenn neu und |Wirkung| > 0,5 min, **oder** wenn sich die Wirkung gegenüber dem zuletzt geloggten Wert ändert (Vergleich mit letztem `auto_balance_day` je Datum; Alt-Einträge über `details.diff_min`). Texte:
  - `"15.10.2026: -9.00h automatisch abgezogen (Soll 9h, Ist 0h, Kein Stempel)"`
  - `"15.10.2026 GEÄNDERT: +9.00h – Tag zählt jetzt +0.00h statt bisher -9.00h (…, Urlaub/Krank)"`
  - weggefallene Tage (z. B. geplanter Abbau gelöscht) → Reason „entfällt“.
- Reasons: „Kein Stempel“ (Ist=0), „unter Soll“, „über Soll“, „Überstundenabbau (Xh)“, „Überstundenabbau (geplant)“, „Offday (… bereits vom Konto abgezogen)“.
- `hr_data.overtime_calc = {baseline_h, diff_h, deduction_h, abbau_h, range_start, at}` wird bei jedem Recompute gespeichert.
- Zusammenfassung bei jeder Saldo-Änderung:
  `"Stundenkonto 2026 automatisch neu berechnet: 104.10h → 120.16h (+16.06h). Ursache: Tagesbilanz -1.94h; Korrektur eines außerhalb der Berechnung geänderten Werts +18.00h. Rechnung: Basiswert … + Tagesbilanz … − Abbau … = …"`
  Ursachen = Delta zu `overtime_calc` (Tagesbilanz, Überstundenabbau, direkte Buchung = Baseline-Änderung, Rest = extern geänderter Wert).

**Fix Frontend `AuditLogSection.jsx`:**
- Neue Labels: `time_manual_correction, time_off_resolve, offday_manual_adjust, offday_create, offday_update, offday_delete, auto_balance_day ("Automatisch · Tag"), auto_balance_recompute ("Automatisch · Konto")`.
- System-Einträge (`performed_by_role==="system"` oder `action` beginnt mit `auto_`) blau hinterlegt.
- Stunden-Badge (grün +/rot −) aus `before/after.overtime_hours`, `after.overtime_delta_h` oder `details.effect_min − previous_effect_min`.
- `truncate` → `break-words`, Untertitel „manuelle Eingriffe und automatische Buchungen des Systems“.

---

## Neue/geänderte Funktionen in `employee.py` (Übersicht)

| Funktion | Zweck |
|---|---|
| `_recompute_overtime_for_year` | + `vacation_entries`, + Abbau-Verbuchung, + `prebooked_offdays` neutral, Offday-Zweig ohne Soll, neues Protokoll, `overtime_calc` |
| `_recompute_and_describe(user_id, start, end)` **neu** | Recompute (force) aller betroffenen Jahre, Text „Jahr: alt → neu“ |
| `offday_overtime_skip_reason(user_id, date)` **neu** | Urlaub/Krank/Abbau/vacation_entries/gestempelt-Prüfung (auch von `offdays.py` genutzt) |
| `_offday_book_overtime(user_id, date, assignment_id)` **neu** | Einsatzplan-Offday: Abzug einmalig auf Baseline + `overtime_deducted_h` am Assignment |
| `_offday_refund_overtime(prev)` **neu** | exakte Rückbuchung, nicht wenn vor manuellem Setzen angelegt |
| `admin_create_time_off`, `admin_delete_time_off`, `resolve_time_off_request` | kein direktes `overtime_hours` mehr, Recompute + Audit |
| `upsert_shift_assignment`, `delete_shift_assignment` | nutzen die Offday-Helper |
| `get_shift_plan` | + Offdays aus `offday_ledger` |

---

## Tests

`backend/tests/test_stundenkonto_bugs_nov2026.py` – 10 Tests, laufen in eigener DB `eventenergie_pytest_stundenkonto` (nie Live-DB), ohne pytest-asyncio (eigener `with_db`-Wrapper mit `asyncio.run`):

```
venv\Scripts\python.exe -m pytest backend/tests/test_stundenkonto_bugs_nov2026.py -q
```

Abgedeckt: Abbau bleibt nach Recompute; stundenweiser geplanter Abbau sofort; Abbau löschen; direkter Urlaub neutral; Offday-Konto nur einmal; Offday-Konto bei Urlaub kein Abzug; Einsatzplan-Offday einmal + Löschen netto 0; Einsatzplan-Offday bei Urlaub kein Abzug; Einsatzplan zeigt Konto-Offday; Protokoll zeigt spätere Tagesänderung.

Hinweise:
- Bestehende `test_time_admin_correction_recompute_bug_b.py` läuft weiter grün (manuell via `asyncio.run`, da kein pytest-asyncio installiert).
- `test_offday_manual_adjust_skip_overtime_bug_a.py` und `test_ueberstundenabbau_teilzeit_display.py` gehen per HTTP gegen den **laufenden Server/Live-DB** – nicht ungeprüft ausführen.

---

## Auswirkung auf Live-Daten (Trockenlauf, Stand 04.11.2026)

Nach dem Deploy springen die Konten beim nächsten Recompute (Stempeln/Änderung). Jeder Sprung wird protokolliert.

| MA | vorher | nachher | Grund |
|---|---|---|---|
| Andre Schoob | 257,41 | 113,41 | Abbau ab 21.09. inkl. Dez. geplant (−153), Offday 18.09. (+9) |
| Martin Mull | 199,63 | 118,63 | Abbau 05.–16.10. (−90), Offday 18.09. (+9) |
| Byron Boretzky | 22,47 | 139,47 | Urlaub nicht mehr abgezogen (+171), Abbau (−54) |
| Timo Hoppen | 296,70 | 251,70 | Abbau Okt. (−36); −9 schon mit altem Code |
| Volker Gutmann | 293,64 | 237,64 | Abbau (−20); −36 schon mit altem Code |
| Christine Ecker | 41,35 | 25,35 | Abbau 06.–09.10. (−16) |
| Dirk / Roberto / Ornela | | −9 / −9 / −12 | Abbau |
| Marcel / Philipp | | +9 / +9 | Urlaub 18.09. / doppelter Offday |

Optional nach Deploy: einmal Recompute (`force=True`) für alle aktiven MA des Jahres, damit die Werte sofort mit Protokoll stehen.

---

## Offene fachliche Fragen (nicht im Code entschieden)

1. **Nachträglich erfasster Abbau vor dem manuellen Setzen:** Andre 10.–13.08. + 14.–15.09. (54h), Byron 17.09. (9h), Dirk 17.09. (9h) wurden *nach* dem manuellen Setzen am 17.09. angelegt. Aktuell: gelten als im gesetzten Wert enthalten (nicht abgezogen). Falls falsch → Regel in `abbau_by_day[...]["counts"]` auf „Tag ≥ range_start ODER Antrag nach `overtime_baseline_set_at`“ ändern.
2. **Andre 12.–14.10.:** krankgemeldet, aber je 9h gestempelt → zählt komplett als Überstunden (+27h). Krankmeldung prüfen.
3. **Christian Ecker:** Recompute ergibt schon mit altem Code −911h (gespeichert 50,61h ist veraltet). Urlaubseintrag 01.04.–02.07. wirkt fehlerhaft; Baseline aus v2-Migration (837,61h). Vor dem nächsten Recompute klären.
4. **Offday-Ledger-Dubletten:** z. B. Andre 10.05. viermal +1 – vermutlich Doppelklicks. Kein Fix eingebaut (evtl. Idempotenz-Sperre für identische manuelle Buchungen innerhalb weniger Sekunden).

---

## Deploy

1. Patch anwenden bzw. Änderungen übernehmen.
2. Backend neu starten.
3. Frontend neu bauen/ausrollen (Einsatzplan + Änderungsprotokoll).
4. Optional: Konten einmal neu berechnen (siehe oben).
