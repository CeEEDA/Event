/**
 * Payroll-Sektion (Lohnabrechnung) aus AdminZeitDetailPage.jsx extrahiert.
 */
import { DollarSign, Save, Download, Trash2, Check } from "lucide-react";
import { Button } from "../../ui/button";

export default function PayrollSection({
  payrollMonth,
  setPayrollMonth,
  loadPayroll,
  loadingPayroll,
  payroll,
  downloadCsv,
  newDeduction,
  setNewDeduction,
  addDeduction,
  removeDeduction,
  releasePayroll,
  releasingPayroll,
  releasedMonths,
}) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4" data-testid="payroll-section">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <DollarSign className="w-4 h-4 text-emerald-600" />
          <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Lohnabrechnung</p>
        </div>
        <div className="flex items-center gap-2">
          <input type="month" value={payrollMonth} onChange={e => setPayrollMonth(e.target.value)}
            className="border border-gray-200 rounded px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-emerald-400" data-testid="payroll-month" />
          <Button onClick={loadPayroll} size="sm" variant="outline" disabled={loadingPayroll} data-testid="calc-payroll-btn">
            {loadingPayroll ? "Berechne..." : "Berechnen"}
          </Button>
          {payroll && (
            <Button onClick={downloadCsv} size="sm" variant="outline" className="text-emerald-700 border-emerald-300 hover:bg-emerald-50" data-testid="download-csv-btn">
              <Download className="w-3.5 h-3.5 mr-1" /> CSV
            </Button>
          )}
        </div>
      </div>
      {payroll && (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[10px] text-gray-400 uppercase tracking-wider">
                  <th className="text-left pb-2 pr-1 font-semibold">Datum</th>
                  <th className="text-left pb-2 px-1 font-semibold">Tag</th>
                  <th className="text-left pb-2 px-1 font-semibold">Von</th>
                  <th className="text-left pb-2 px-1 font-semibold">Bis</th>
                  <th className="text-right pb-2 px-1 font-semibold">Std.</th>
                  <th className="text-left pb-2 px-1 font-semibold">Typ</th>
                  <th className="text-right pb-2 px-1 font-semibold">Nacht</th>
                  <th className="text-right pb-2 px-1 font-semibold">Grund</th>
                  <th className="text-right pb-2 px-1 font-semibold">Zuschlag</th>
                  <th className="text-right pb-2 pl-1 font-semibold">Gesamt</th>
                </tr>
              </thead>
              <tbody>
                {payroll.rows.map((r, i) => {
                  const typeColors = {
                    regular: "text-gray-500", sunday: "text-orange-600", holiday: "text-red-600", special: "text-red-700 font-bold",
                  };
                  const typeLabels = { regular: "Normal", sunday: "Sonntag", holiday: "Feiertag", special: "Bes. Feiertag" };
                  return (
                    <tr key={i} className="border-t border-gray-50">
                      <td className="py-1 pr-1 text-gray-700">{new Date(r.date + "T00:00").toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" })}</td>
                      <td className="py-1 px-1 text-gray-500">{r.weekday}</td>
                      <td className="py-1 px-1">{r.clock_in}</td>
                      <td className="py-1 px-1">{r.clock_out}</td>
                      <td className="py-1 px-1 text-right font-medium">{r.total_hours.toFixed(1)}</td>
                      <td className={`py-1 px-1 text-[10px] font-semibold ${typeColors[r.surcharge_type]}`}>
                        {typeLabels[r.surcharge_type]}{r.holiday_name ? ` (${r.holiday_name})` : ""}
                      </td>
                      <td className="py-1 px-1 text-right">{r.night_min > 0 ? <span className="text-violet-600">{Math.round(r.night_min / 6) / 10}h</span> : "—"}</td>
                      <td className="py-1 px-1 text-right">{r.base_wage.toFixed(2)}€</td>
                      <td className="py-1 px-1 text-right text-orange-600">{(r.surcharge_wage + r.night_wage) > 0 ? `+${(r.surcharge_wage + r.night_wage).toFixed(2)}€` : "—"}</td>
                      <td className="py-1 pl-1 text-right font-bold">{r.total_wage.toFixed(2)}€</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="mt-3 pt-3 border-t border-gray-200 grid grid-cols-2 sm:grid-cols-3 gap-2">
            <div className="bg-gray-50 rounded-lg p-2.5 text-center">
              <p className="text-[10px] text-gray-400 uppercase font-semibold">Grundlohn</p>
              <p className="text-lg font-bold text-gray-800">{payroll.totals.regular_wage?.toFixed(2)}€</p>
            </div>
            <div className="bg-orange-50 rounded-lg p-2.5 text-center">
              <p className="text-[10px] text-orange-500 uppercase font-semibold">Nachtzuschlag</p>
              <p className="text-lg font-bold text-orange-700">
                {(payroll.totals.night_wage || 0).toFixed(2)}€
              </p>
            </div>
            <div className="bg-emerald-50 rounded-lg p-2.5 text-center">
              <p className="text-[10px] text-emerald-500 uppercase font-semibold">Brutto Gesamt</p>
              <p className="text-lg font-bold text-emerald-700">{payroll.total_gross?.toFixed(2)}€</p>
            </div>
          </div>

          {/* Deductions / Abzüge */}
          <div className="mt-3 pt-3 border-t border-gray-200">
            <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-2">Abzüge</p>
            {(payroll.deductions || []).map(d => (
              <div key={d.id} className="flex items-center gap-2 py-1 group">
                <span className="text-sm text-gray-700 flex-1">{d.text}</span>
                <span className="text-sm font-bold text-red-600">-{parseFloat(d.amount).toFixed(2)}€</span>
                <button onClick={() => removeDeduction(d.id)} className="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500" data-testid={`remove-deduction-${d.id}`}>
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            ))}
            <div className="flex items-center gap-2 mt-2">
              <input type="text" placeholder="z.B. Arbeitshose" value={newDeduction.text} onChange={e => setNewDeduction(p => ({ ...p, text: e.target.value }))}
                className="flex-1 border border-gray-200 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-red-300" data-testid="deduction-text" />
              <input type="number" step="0.01" min="0" placeholder="Betrag" value={newDeduction.amount} onChange={e => setNewDeduction(p => ({ ...p, amount: e.target.value }))}
                className="w-24 border border-gray-200 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-red-300" data-testid="deduction-amount" />
              <Button onClick={addDeduction} size="sm" variant="outline" className="text-red-600 border-red-200 hover:bg-red-50" data-testid="add-deduction-btn">
                <span className="text-base font-bold mr-1">−</span> Abzug
              </Button>
            </div>
          </div>

          {/* Net total */}
          {(payroll.total_deductions || 0) > 0 && (
            <div className="mt-3 pt-3 border-t border-gray-200 flex items-center justify-between">
              <span className="text-sm font-semibold text-gray-700">Netto Auszahlung</span>
              <span className="text-xl font-bold text-emerald-700">{payroll.total_net?.toFixed(2)}€</span>
            </div>
          )}

          {/* Release Button */}
          <div className="mt-4 pt-3 border-t border-gray-200 flex items-center justify-between">
            <div className="flex items-center gap-2">
              {releasedMonths[payrollMonth] && (
                <span className="text-xs text-green-600 flex items-center gap-1">
                  <Check className="w-3.5 h-3.5" /> Freigegeben am {new Date(releasedMonths[payrollMonth]).toLocaleDateString("de-DE")}
                </span>
              )}
            </div>
            <Button onClick={releasePayroll} disabled={releasingPayroll || !payroll} size="sm" className="bg-green-600 hover:bg-green-700" data-testid="release-payroll-btn">
              <Save className="w-3.5 h-3.5 mr-1.5" /> {releasingPayroll ? "Wird freigegeben..." : "Speichern & Freigeben"}
            </Button>
          </div>
        </>
      )}
      {!payroll && !loadingPayroll && (
        <p className="text-sm text-gray-400 text-center py-4">Monat auswählen und "Berechnen" klicken</p>
      )}
    </div>
  );
}
