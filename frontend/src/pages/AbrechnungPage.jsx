import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import api, { BACKEND_URL } from "../lib/api";
import { ArrowLeft, Receipt, ChevronDown, ChevronUp, DollarSign, FileText, Download, Eye } from "lucide-react";

const API = BACKEND_URL;

export default function AbrechnungPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const token = localStorage.getItem("token");
  const [releases, setReleases] = useState([]);
  const [payrollDocs, setPayrollDocs] = useState([]);
  const [expandedMonth, setExpandedMonth] = useState(null);

  useEffect(() => {
    api.get(`/employee/payroll/my-releases?token=${token}`)
      .then(r => setReleases(r.data || []))
      .catch(() => {});
    api.get(`/employee/payroll/my-documents?token=${token}`)
      .then(r => setPayrollDocs(r.data || []))
      .catch(() => {});
  }, [token]);

  const monthLabel = (m) => {
    if (!m) return "Unbekannt";
    const [y, mo] = m.split("-");
    return new Date(parseInt(y), parseInt(mo) - 1).toLocaleDateString("de-DE", { month: "long", year: "numeric" });
  };

  return (
    <div className="min-h-screen bg-gray-50" data-testid="abrechnung-page">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-3xl mx-auto px-4 py-3 flex items-center gap-3">
          <button onClick={() => navigate("/mitarbeiter-daten")} className="text-gray-500 hover:text-gray-700" data-testid="back-btn">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <Receipt className="w-5 h-5 text-emerald-600" />
          <h1 className="text-lg font-semibold text-gray-900">Meine Abrechnungen</h1>
        </div>
      </header>

      <div className="max-w-3xl mx-auto px-4 py-5 space-y-6">

        {/* DATEV Lohnabrechnungen (PDFs) */}
        {payrollDocs.length > 0 && (
          <div data-testid="datev-payroll-section">
            <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-3">Lohnabrechnungen (DATEV)</p>
            <div className="space-y-2">
              {payrollDocs.map(doc => (
                <div key={doc.id} className="bg-white rounded-xl border border-gray-200 px-4 py-3 flex items-center justify-between" data-testid={`datev-doc-${doc.id}`}>
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-lg bg-green-100 flex items-center justify-center">
                      <FileText className="w-4 h-4 text-green-600" />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-gray-900">{doc.payroll_month ? monthLabel(doc.payroll_month) : doc.original_filename}</p>
                      <p className="text-xs text-gray-400">
                        {doc.payroll_net_amount ? `Netto: ${parseFloat(doc.payroll_net_amount).toFixed(2)}€` : ""}
                        {doc.payroll_info?.personnel_number ? ` · Pers.-Nr. ${doc.payroll_info.personnel_number}` : ""}
                      </p>
                    </div>
                  </div>
                  <a
                    href={`${API}/api/documents/${doc.id}/file`}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-1.5 text-sm text-emerald-600 hover:text-emerald-700 font-medium"
                    data-testid={`view-doc-${doc.id}`}
                  >
                    <Eye className="w-4 h-4" /> Ansehen
                  </a>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Interne Abrechnungen (freigegebene Kalkulationen) */}
        {releases.length > 0 && (
          <div data-testid="internal-payroll-section">
            <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-3">Interne Abrechnungen</p>
            <div className="space-y-2">
              {releases.map(rel => {
                const p = rel.payroll_data;
                if (!p) return null;
                const isOpen = expandedMonth === rel.month;
                return (
                  <div key={rel.month} className="bg-white rounded-xl border border-gray-200 overflow-hidden" data-testid={`release-${rel.month}`}>
                    <button
                      onClick={() => setExpandedMonth(isOpen ? null : rel.month)}
                      className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 transition-colors"
                      data-testid={`toggle-${rel.month}`}
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-lg bg-emerald-100 flex items-center justify-center">
                          <DollarSign className="w-4 h-4 text-emerald-600" />
                        </div>
                        <div className="text-left">
                          <p className="text-sm font-semibold text-gray-900">{monthLabel(rel.month)}</p>
                          <p className="text-xs text-gray-400">Freigegeben am {new Date(rel.released_at).toLocaleDateString("de-DE")}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="text-lg font-bold text-emerald-700">{p.total_net?.toFixed(2)}€</span>
                        {isOpen ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
                      </div>
                    </button>

                    {isOpen && (
                      <div className="px-4 pb-4 border-t border-gray-100">
                        <table className="w-full text-xs mt-3">
                          <thead>
                            <tr className="text-[10px] text-gray-400 uppercase">
                              <th className="text-left py-1">Datum</th>
                              <th className="text-left">Tag</th>
                              <th className="text-left">Von</th>
                              <th className="text-left">Bis</th>
                              <th className="text-right">Std.</th>
                              <th className="text-left pl-2">Typ</th>
                              <th className="text-right">Nacht</th>
                              <th className="text-right">Grund</th>
                              <th className="text-right">Zuschlag</th>
                              <th className="text-right">Gesamt</th>
                            </tr>
                          </thead>
                          <tbody>
                            {(p.rows || []).map((r, i) => (
                              <tr key={i} className="border-t border-gray-50">
                                <td className="py-1.5 text-gray-700">{r.date}</td>
                                <td className="text-gray-500">{r.weekday}</td>
                                <td className="text-gray-700">{r.start}</td>
                                <td className="text-gray-700">{r.end}</td>
                                <td className="text-right text-gray-700">{r.hours?.toFixed(1)}</td>
                                <td className="pl-2">
                                  {r.type === "Sonntag" && <span className="text-orange-600 text-[10px]">{r.type_label || r.type}</span>}
                                  {r.type === "Feiertag" && <span className="text-purple-600 text-[10px]">{r.type_label || r.type}</span>}
                                  {r.type === "Sonderfeiertag" && <span className="text-red-600 text-[10px]">{r.type_label || r.type}</span>}
                                  {!["Sonntag", "Feiertag", "Sonderfeiertag"].includes(r.type) && <span className="text-gray-400 text-[10px]">{r.type_label || r.type || "—"}</span>}
                                </td>
                                <td className="text-right">{r.night_hours > 0 ? <span className="text-indigo-600">{r.night_hours?.toFixed(1)}h</span> : <span className="text-gray-300">—</span>}</td>
                                <td className="text-right text-gray-700">{r.base_wage?.toFixed(2)}€</td>
                                <td className="text-right">{r.surcharge > 0 ? <span className="text-orange-600">+{r.surcharge?.toFixed(2)}€</span> : <span className="text-gray-300">—</span>}</td>
                                <td className="text-right font-medium text-gray-900">{r.total_wage?.toFixed(2)}€</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                        <div className="grid grid-cols-3 gap-2 mt-4">
                          <div className="bg-gray-50 rounded-lg p-2.5 text-center">
                            <p className="text-[10px] text-gray-400 uppercase font-medium">Grundlohn</p>
                            <p className="text-base font-bold text-gray-800">{p.totals?.regular_wage?.toFixed(2)}€</p>
                          </div>
                          <div className="bg-amber-50 rounded-lg p-2.5 text-center">
                            <p className="text-[10px] text-orange-500 uppercase font-medium">Zuschläge</p>
                            <p className="text-base font-bold text-orange-700">
                              {((p.totals?.sunday_wage || 0) + (p.totals?.holiday_wage || 0) + (p.totals?.special_wage || 0) + (p.totals?.night_wage || 0)).toFixed(2)}€
                            </p>
                          </div>
                          <div className="bg-green-50 rounded-lg p-2.5 text-center">
                            <p className="text-[10px] text-green-600 uppercase font-medium">Brutto Gesamt</p>
                            <p className="text-base font-bold text-green-800">{p.total_gross?.toFixed(2)}€</p>
                          </div>
                        </div>
                        {p.deductions && p.deductions.length > 0 && (
                          <div className="mt-3 pt-3 border-t border-gray-100">
                            <p className="text-[10px] text-gray-400 uppercase font-medium mb-2">Abzüge</p>
                            {p.deductions.map((d, i) => (
                              <div key={i} className="flex justify-between py-1 text-sm">
                                <span className="text-gray-700">{d.text || d.description}</span>
                                <span className="text-red-600 font-medium">-{parseFloat(d.amount).toFixed(2)}€</span>
                              </div>
                            ))}
                          </div>
                        )}
                        <div className="mt-3 pt-3 border-t border-gray-200 flex items-center justify-between">
                          <span className="text-sm font-bold text-gray-700">Netto Auszahlung</span>
                          <span className="text-xl font-bold text-emerald-700">{p.total_net?.toFixed(2)}€</span>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {releases.length === 0 && payrollDocs.length === 0 && (
          <p className="text-sm text-gray-400 text-center py-8" data-testid="no-releases">Noch keine Abrechnungen vorhanden.</p>
        )}
      </div>
    </div>
  );
}
