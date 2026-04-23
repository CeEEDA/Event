import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { CalendarDays, MapPin, Zap, ArrowLeft, ArrowRight, Plus, Home, UserCircle2 } from "lucide-react";
import { PAYMENT_METHODS } from "./constants";

export function SignupForm({ selectedEvent, signupForm, setSignupForm, additionalSignups, setAdditionalSignups, depositAmounts, schausteller, agbAccepted, setAgbAccepted, setShowAgb, onSubmit, onBack, saving }) {
  const regularPrices = selectedEvent.prices || [];
  const wwPrices = selectedEvent.wohnwagen_prices || [];
  const isRechnung = signupForm.payment_method === "rechnung";

  // Build booking summary
  const mainPrice = regularPrices.find(p => p.connection_type === signupForm.connection_type);
  const summaryItems = [];
  if (mainPrice) {
    summaryItems.push({ label: `${signupForm.fahrgeschaeft || "Hauptanschluss"} – ${signupForm.connection_type}`, price: mainPrice.price });
    if (!isRechnung) {
      const dep = depositAmounts[signupForm.connection_type] || 0;
      if (dep > 0) summaryItems.push({ label: `Kaution ${signupForm.connection_type}`, price: dep, isDeposit: true });
    }
  }
  additionalSignups.forEach((a, i) => {
    const priceList = a.isWohnwagen ? wwPrices : regularPrices;
    const p = priceList.find(pr => pr.connection_type === a.connection_type);
    if (p) {
      summaryItems.push({ label: `${a.isWohnwagen ? "Wohnwagen" : (a.fahrgeschaeft || `${i+2}. Anschluss`)} – ${a.connection_type}`, price: p.price });
      if (!isRechnung && !a.isWohnwagen) {
        const dep = depositAmounts[a.connection_type] || 0;
        if (dep > 0) summaryItems.push({ label: `Kaution ${a.connection_type}`, price: dep, isDeposit: true });
      }
    }
  });
  const totalNetto = summaryItems.reduce((sum, item) => sum + item.price, 0);

  return (
    <div data-testid="signup-step">
      <button onClick={onBack} className="flex items-center gap-1 text-sm text-gray-500 hover:text-fuchsia-600 mb-4" data-testid="back-events-btn">
        <ArrowLeft className="w-4 h-4" /> Zurück zur Auswahl
      </button>
      {schausteller && (schausteller.name || schausteller.firma) && (
        <div className="mb-3 flex items-center gap-2 px-3 py-2 rounded-lg bg-fuchsia-50 border border-fuchsia-200 text-sm" data-testid="signup-angemeldet-als">
          <UserCircle2 className="w-4 h-4 text-fuchsia-600 flex-shrink-0" />
          <span className="text-gray-500">Angemeldet als:</span>
          <span className="font-semibold text-fuchsia-800 truncate">
            {[schausteller.name, schausteller.firma].filter(Boolean).join(" · ")}
          </span>
        </div>
      )}
      <div className="bg-white border border-gray-200 rounded-xl p-6 space-y-5">
        <div>
          <h2 className="text-lg font-bold text-gray-900 mb-1">{selectedEvent.name}</h2>
          <div className="flex flex-wrap gap-3 text-xs text-gray-500">
            {selectedEvent.location && <span className="flex items-center gap-1"><MapPin className="w-3 h-3" /> {selectedEvent.location}</span>}
            <span className="flex items-center gap-1"><CalendarDays className="w-3 h-3" />{new Date(selectedEvent.start_date).toLocaleDateString("de-DE")} – {new Date(selectedEvent.end_date).toLocaleDateString("de-DE")}</span>
          </div>
        </div>
        <div className="border-t border-gray-100 pt-4 space-y-4">
          <div><Label className="text-gray-700 text-sm">Platznummer *</Label><Input value={signupForm.platznummer} onChange={e => setSignupForm(f => ({ ...f, platznummer: e.target.value }))} placeholder="z.B. A12" className="mt-1" data-testid="signup-platznummer" /></div>
          <div><Label className="text-gray-700 text-sm">Fahrgeschäft / Betrieb *</Label><Input value={signupForm.fahrgeschaeft} onChange={e => setSignupForm(f => ({ ...f, fahrgeschaeft: e.target.value }))} placeholder="z.B. Achterbahn, Autoscooter, Imbiss" className="mt-1" data-testid="signup-fahrgeschaeft" /></div>
          <div>
            <Label className="text-gray-700 text-sm">Stromanschluss *</Label>
            <div className="grid grid-cols-3 gap-2 mt-1">
              {regularPrices.map(p => (
                <button key={p.connection_type} onClick={() => setSignupForm(f => ({ ...f, connection_type: p.connection_type }))}
                  className={`p-3 rounded-lg border text-center transition-colors ${signupForm.connection_type === p.connection_type ? "border-fuchsia-500 bg-fuchsia-50 text-fuchsia-700" : "border-gray-200 text-gray-600 hover:border-gray-300"}`}
                  data-testid={`conn-${p.connection_type}`}>
                  <Zap className="w-4 h-4 mx-auto mb-1" />
                  <span className="text-xs font-medium block">{p.connection_type}</span>
                  <span className="text-[10px] text-gray-400 block">{p.price.toFixed(2)} EUR</span>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Zusätzliche Anschlüsse */}
        {additionalSignups.map((extra, idx) => (
          <div key={idx} className={`border rounded-xl p-4 space-y-4 relative ${extra.isWohnwagen ? "border-amber-200" : "border-gray-200"}`} data-testid={`extra-signup-${idx}`}>
            <div className="flex items-center justify-between mb-1">
              <span className={`text-xs font-semibold uppercase tracking-wider ${extra.isWohnwagen ? "text-amber-600" : "text-gray-500"}`}>
                {extra.isWohnwagen ? `Wohnwagen ${idx + 1}` : `${idx + 2}. Anschluss`}
              </span>
              <button onClick={() => setAdditionalSignups(prev => prev.filter((_, i) => i !== idx))} className="text-xs text-red-400 hover:text-red-600" data-testid={`remove-extra-${idx}`}>Entfernen</button>
            </div>
            {extra.isWohnwagen ? (
              <>
                <div><Label className="text-gray-700 text-sm">Position / Platznummer</Label><Input value={extra.platznummer} onChange={e => { const v = e.target.value; setAdditionalSignups(prev => prev.map((s, i) => i === idx ? { ...s, platznummer: v } : s)); }} className="mt-1" placeholder="z.B. A15" data-testid={`extra-platznummer-${idx}`} /></div>
                <div>
                  <Label className="text-gray-700 text-sm">Anschluss</Label>
                  <div className="grid grid-cols-3 gap-2 mt-1">
                    {wwPrices.map(p => (
                      <button key={p.connection_type} type="button" onClick={() => setAdditionalSignups(prev => prev.map((s, i) => i === idx ? { ...s, connection_type: p.connection_type } : s))}
                        className={`p-2.5 rounded-lg border text-center transition-colors ${extra.connection_type === p.connection_type ? "border-amber-500 bg-amber-100 text-amber-700" : "border-gray-200 text-gray-600 hover:border-gray-300 bg-white"}`}
                        data-testid={`extra-conn-ww-${idx}-${p.connection_type}`}>
                        <Home className="w-3.5 h-3.5 mx-auto mb-0.5" />
                        <span className="text-xs font-medium block">{p.connection_type}</span>
                        <span className="text-[10px] text-gray-400 block">{p.price.toFixed(2)} EUR</span>
                      </button>
                    ))}
                  </div>
                </div>
              </>
            ) : (
              <>
                <div><Label className="text-gray-700 text-sm">Platznummer *</Label><Input value={extra.platznummer} onChange={e => { const v = e.target.value; setAdditionalSignups(prev => prev.map((s, i) => i === idx ? { ...s, platznummer: v } : s)); }} className="mt-1" placeholder="z.B. A12" data-testid={`extra-platznummer-${idx}`} /></div>
                <div><Label className="text-gray-700 text-sm">Fahrgeschäft / Betrieb *</Label><Input value={extra.fahrgeschaeft} onChange={e => { const v = e.target.value; setAdditionalSignups(prev => prev.map((s, i) => i === idx ? { ...s, fahrgeschaeft: v } : s)); }} className="mt-1" placeholder="z.B. Achterbahn, Autoscooter, Imbiss" data-testid={`extra-fahrgeschaeft-${idx}`} /></div>
                <div>
                  <Label className="text-gray-700 text-sm">Stromanschluss *</Label>
                  <div className="grid grid-cols-3 gap-2 mt-1">
                    {regularPrices.map(p => (
                      <button key={p.connection_type} type="button" onClick={() => setAdditionalSignups(prev => prev.map((s, i) => i === idx ? { ...s, connection_type: p.connection_type } : s))}
                        className={`p-3 rounded-lg border text-center transition-colors ${extra.connection_type === p.connection_type ? "border-fuchsia-500 bg-fuchsia-50 text-fuchsia-700" : "border-gray-200 text-gray-600 hover:border-gray-300 bg-white"}`}
                        data-testid={`extra-conn-${idx}-${p.connection_type}`}>
                        <Zap className="w-4 h-4 mx-auto mb-1" />
                        <span className="text-xs font-medium block">{p.connection_type}</span>
                        <span className="text-[10px] text-gray-400 block">{p.price.toFixed(2)} EUR</span>
                      </button>
                    ))}
                  </div>
                </div>
              </>
            )}
          </div>
        ))}

        {/* Buttons */}
        <div className="flex flex-col gap-2">
          <button type="button" onClick={() => setAdditionalSignups(prev => [...prev, { platznummer: "", fahrgeschaeft: "", connection_type: "", payment_method: signupForm.payment_method, isWohnwagen: false }])}
            className="flex-1 flex items-center justify-center gap-2 px-3 py-2.5 border-2 border-dashed border-fuchsia-300 rounded-lg text-sm font-medium text-fuchsia-600 hover:bg-fuchsia-50 hover:border-fuchsia-400 transition-colors" data-testid="add-extra-signup-btn">
            <Plus className="w-4 h-4" /> Weiteren Anschluss anmelden
          </button>
          <button type="button" onClick={() => setAdditionalSignups(prev => [...prev, { platznummer: "", fahrgeschaeft: "Wohnwagen", connection_type: "", payment_method: signupForm.payment_method, isWohnwagen: true }])}
            className="flex-1 flex items-center justify-center gap-2 px-3 py-2.5 border-2 border-dashed border-amber-300 rounded-lg text-sm font-medium text-amber-600 hover:bg-amber-50 hover:border-amber-400 transition-colors" data-testid="add-wohnwagen-btn">
            <Plus className="w-4 h-4" /> Wohnwagen-Anschluss anmelden
          </button>
        </div>

        {/* Zahlungsmittel */}
        <div>
          <Label className="text-gray-700 text-sm">Zahlungsmittel</Label>
          <select value={signupForm.payment_method} onChange={e => setSignupForm(f => ({ ...f, payment_method: e.target.value }))} className="w-full mt-1 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-fuchsia-500 bg-white" data-testid="signup-payment">
            {PAYMENT_METHODS.filter(m => m.value !== "rechnung" || schausteller?.kauf_auf_rechnung).map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
          </select>
        </div>

        {/* Buchungsübersicht */}
        {summaryItems.length > 0 && (
          <div className="border border-fuchsia-200 rounded-xl p-4 space-y-3" data-testid="booking-summary">
            <Label className="text-gray-700 text-sm font-semibold">Buchungsübersicht</Label>
            <div className="space-y-1.5">
              {summaryItems.map((item, i) => (
                <div key={i} className="flex justify-between text-sm">
                  <span className={item.isDeposit ? "text-amber-600" : "text-gray-600"}>{item.label}</span>
                  <span className={`font-medium ${item.isDeposit ? "text-amber-700" : "text-gray-800"}`}>{item.price.toFixed(2)} EUR</span>
                </div>
              ))}
              <div className="border-t border-gray-200 pt-2 mt-2 flex justify-between">
                <span className="text-sm font-bold text-gray-900">Gesamt (netto)</span>
                <span className="text-lg font-bold text-fuchsia-700">{totalNetto.toFixed(2)} EUR</span>
              </div>
            </div>
          </div>
        )}

        {/* AGB */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <label className="flex items-start gap-3 cursor-pointer">
            <input type="checkbox" checked={agbAccepted} onChange={e => setAgbAccepted(e.target.checked)} className="mt-0.5 w-5 h-5 rounded border-blue-300 text-blue-600 focus:ring-blue-500 flex-shrink-0" data-testid="agb-checkbox" />
            <span className="text-sm text-blue-900">
              Hiermit akzeptiere ich die{" "}
              <button type="button" onClick={(e) => { e.preventDefault(); setShowAgb(true); }} className="text-blue-600 font-semibold underline hover:text-blue-800" data-testid="agb-link">
                AGB's der Eventenergie Deutschland GmbH & Co. KG
              </button>
            </span>
          </label>
        </div>

        <Button onClick={onSubmit} disabled={saving || !agbAccepted} className="w-full bg-fuchsia-600 hover:bg-fuchsia-700 text-white disabled:opacity-50" data-testid="submit-signup-btn">
          {saving ? "Wird angemeldet..." : "Verbindlich anmelden"} <ArrowRight className="w-4 h-4 ml-1" />
        </Button>
      </div>
    </div>
  );
}
