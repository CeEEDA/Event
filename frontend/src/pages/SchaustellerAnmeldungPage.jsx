import { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { Logo } from "../components/Logo";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { CalendarDays, MapPin, Zap, Check, ArrowRight, ArrowLeft, UserPlus, LogIn } from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const api = {
  post: (path, data) => fetch(`${BACKEND_URL}/api${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) }).then(async r => { const d = await r.json(); if (!r.ok) throw { response: { data: d } }; return { data: d }; }),
  get: (path) => fetch(`${BACKEND_URL}/api${path}`).then(async r => { const d = await r.json(); if (!r.ok) throw { response: { data: d } }; return { data: d }; }),
};

const PAYMENT_METHODS = [
  { value: "kreditkarte", label: "Kreditkarte" },
  { value: "paypal", label: "PayPal" },
  { value: "rechnung", label: "Auf Rechnung" },
];

export default function SchaustellerAnmeldungPage() {
  const [searchParams] = useSearchParams();
  const preselectedEvent = searchParams.get("event");

  // Steps: auth -> event -> signup -> done
  const [step, setStep] = useState("auth");
  const [authMode, setAuthMode] = useState("register"); // register or login
  const [schausteller, setSchausteller] = useState(null);
  const [events, setEvents] = useState([]);
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [saving, setSaving] = useState(false);

  // Registration form
  const [regForm, setRegForm] = useState({
    firma: "", name: "", strasse: "", plz: "", ort: "",
    steuernummer: "", email: "", telefon: "", rechnungs_email: "",
  });
  const [loginEmail, setLoginEmail] = useState("");

  // Signup form
  const [signupForm, setSignupForm] = useState({
    platznummer: "", fahrgeschaeft: "", connection_type: "", payment_method: "kreditkarte",
  });

  // Load events when step is "event"
  useEffect(() => {
    if (step === "event" || step === "auth") {
      api.get("/kirmes/public/events").then(r => {
        setEvents(r.data);
        if (preselectedEvent) {
          const found = r.data.find(e => e.id === preselectedEvent);
          if (found) {
            setSelectedEvent(found);
            if (step === "event") setStep("signup");
          }
        }
      }).catch(() => {});
    }
  }, [step, preselectedEvent]);

  const handleRegister = async () => {
    if (!regForm.firma || !regForm.name || !regForm.email || !regForm.rechnungs_email) {
      toast.error("Bitte alle Pflichtfelder ausfüllen");
      return;
    }
    setSaving(true);
    try {
      const r = await api.post("/kirmes/public/register", regForm);
      setSchausteller(r.data);
      toast.success("Registrierung erfolgreich!");
      if (preselectedEvent && selectedEvent) {
        setStep("signup");
      } else {
        setStep("event");
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || "Fehler bei der Registrierung");
    } finally { setSaving(false); }
  };

  const handleLogin = async () => {
    if (!loginEmail) { toast.error("Bitte E-Mail eingeben"); return; }
    setSaving(true);
    try {
      const r = await api.post(`/kirmes/public/login?email=${encodeURIComponent(loginEmail)}`, {});
      setSchausteller(r.data);
      toast.success(`Willkommen zurück, ${r.data.name}!`);
      if (preselectedEvent && selectedEvent) {
        setStep("signup");
      } else {
        setStep("event");
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || "Fehler bei der Anmeldung");
    } finally { setSaving(false); }
  };

  const handleSignup = async () => {
    if (!signupForm.platznummer || !signupForm.fahrgeschaeft || !signupForm.connection_type) {
      toast.error("Bitte Platznummer, Fahrgeschäft und Anschluss angeben");
      return;
    }
    setSaving(true);
    try {
      await api.post("/kirmes/public/signup", {
        event_id: selectedEvent.id,
        schausteller_id: schausteller.id,
        ...signupForm,
      });
      toast.success("Anmeldung erfolgreich!");
      setStep("done");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Fehler bei der Anmeldung");
    } finally { setSaving(false); }
  };

  const getPrice = () => {
    if (!selectedEvent || !signupForm.connection_type) return null;
    const p = (selectedEvent.prices || []).find(p => p.connection_type === signupForm.connection_type);
    return p ? p.price : null;
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col" data-testid="schausteller-anmeldung">
      <header className="bg-white border-b border-gray-200 p-4">
        <div className="max-w-lg mx-auto flex items-center justify-between">
          <Logo size="normal" />
          <p className="text-xs text-gray-400">Schausteller-Portal</p>
        </div>
      </header>

      <main className="flex-1 flex items-start justify-center p-4 pt-8">
        <div className="w-full max-w-lg">

          {/* Step: Auth (Register or Login) */}
          {step === "auth" && (
            <div className="bg-white border border-gray-200 rounded-xl p-6" data-testid="auth-step">
              <div className="text-center mb-6">
                <h1 className="text-xl font-bold text-gray-900 mb-1">Schausteller-Anmeldung</h1>
                <p className="text-sm text-gray-500">Registrieren Sie sich einmalig oder melden Sie sich an</p>
              </div>

              <div className="flex gap-2 mb-6">
                <button
                  onClick={() => setAuthMode("register")}
                  className={`flex-1 py-2 rounded-lg text-sm font-medium transition-colors ${authMode === "register" ? "bg-fuchsia-600 text-white" : "bg-gray-100 text-gray-600"}`}
                  data-testid="auth-register-tab"
                >
                  <UserPlus className="w-4 h-4 inline mr-1" /> Registrieren
                </button>
                <button
                  onClick={() => setAuthMode("login")}
                  className={`flex-1 py-2 rounded-lg text-sm font-medium transition-colors ${authMode === "login" ? "bg-fuchsia-600 text-white" : "bg-gray-100 text-gray-600"}`}
                  data-testid="auth-login-tab"
                >
                  <LogIn className="w-4 h-4 inline mr-1" /> Anmelden
                </button>
              </div>

              {authMode === "register" ? (
                <div className="space-y-3" data-testid="register-form">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <Label className="text-gray-700 text-sm">Firma *</Label>
                      <Input value={regForm.firma} onChange={e => setRegForm(f => ({ ...f, firma: e.target.value }))} className="mt-1" data-testid="reg-firma" />
                    </div>
                    <div>
                      <Label className="text-gray-700 text-sm">Name *</Label>
                      <Input value={regForm.name} onChange={e => setRegForm(f => ({ ...f, name: e.target.value }))} className="mt-1" data-testid="reg-name" />
                    </div>
                  </div>
                  <div>
                    <Label className="text-gray-700 text-sm">Straße</Label>
                    <Input value={regForm.strasse} onChange={e => setRegForm(f => ({ ...f, strasse: e.target.value }))} className="mt-1" data-testid="reg-strasse" />
                  </div>
                  <div className="grid grid-cols-3 gap-3">
                    <div>
                      <Label className="text-gray-700 text-sm">PLZ</Label>
                      <Input value={regForm.plz} onChange={e => setRegForm(f => ({ ...f, plz: e.target.value }))} className="mt-1" data-testid="reg-plz" />
                    </div>
                    <div className="col-span-2">
                      <Label className="text-gray-700 text-sm">Ort</Label>
                      <Input value={regForm.ort} onChange={e => setRegForm(f => ({ ...f, ort: e.target.value }))} className="mt-1" data-testid="reg-ort" />
                    </div>
                  </div>
                  <div>
                    <Label className="text-gray-700 text-sm">Steuernummer</Label>
                    <Input value={regForm.steuernummer} onChange={e => setRegForm(f => ({ ...f, steuernummer: e.target.value }))} className="mt-1" data-testid="reg-steuernummer" />
                  </div>
                  <div>
                    <Label className="text-gray-700 text-sm">E-Mail *</Label>
                    <Input type="email" value={regForm.email} onChange={e => setRegForm(f => ({ ...f, email: e.target.value }))} className="mt-1" data-testid="reg-email" />
                  </div>
                  <div>
                    <Label className="text-gray-700 text-sm">Telefon</Label>
                    <Input value={regForm.telefon} onChange={e => setRegForm(f => ({ ...f, telefon: e.target.value }))} className="mt-1" data-testid="reg-telefon" />
                  </div>
                  <div>
                    <Label className="text-gray-700 text-sm">Rechnungs-E-Mail *</Label>
                    <Input type="email" value={regForm.rechnungs_email} onChange={e => setRegForm(f => ({ ...f, rechnungs_email: e.target.value }))} placeholder="Falls abweichend" className="mt-1" data-testid="reg-rechnungs-email" />
                    <p className="text-[10px] text-gray-400 mt-1">Rechnungen werden an diese Adresse versendet</p>
                  </div>
                  <Button onClick={handleRegister} disabled={saving} className="w-full bg-fuchsia-600 hover:bg-fuchsia-700 text-white mt-2" data-testid="register-btn">
                    {saving ? "Wird registriert..." : "Registrieren"} <ArrowRight className="w-4 h-4 ml-1" />
                  </Button>
                </div>
              ) : (
                <div className="space-y-4" data-testid="login-form">
                  <div>
                    <Label className="text-gray-700 text-sm">E-Mail</Label>
                    <Input type="email" value={loginEmail} onChange={e => setLoginEmail(e.target.value)} placeholder="Ihre registrierte E-Mail" className="mt-1" data-testid="login-email" />
                  </div>
                  <Button onClick={handleLogin} disabled={saving} className="w-full bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="login-btn">
                    {saving ? "Wird geprüft..." : "Anmelden"} <ArrowRight className="w-4 h-4 ml-1" />
                  </Button>
                </div>
              )}
            </div>
          )}

          {/* Step: Select Event */}
          {step === "event" && (
            <div data-testid="event-step">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-bold text-gray-900">Veranstaltung wählen</h2>
                <p className="text-sm text-gray-500">Hallo, {schausteller?.name}</p>
              </div>
              {events.length === 0 ? (
                <div className="bg-white border border-gray-200 rounded-xl p-8 text-center text-gray-400">
                  Aktuell keine Veranstaltungen verfügbar
                </div>
              ) : (
                <div className="space-y-3">
                  {events.map(event => (
                    <button
                      key={event.id}
                      onClick={() => { setSelectedEvent(event); setStep("signup"); }}
                      className="w-full bg-white border border-gray-200 rounded-xl p-4 text-left hover:border-fuchsia-400 transition-colors"
                      data-testid={`select-event-${event.id}`}
                    >
                      <h3 className="font-semibold text-gray-900 mb-1">{event.name}</h3>
                      <div className="flex flex-wrap gap-3 text-xs text-gray-500">
                        {event.location && <span className="flex items-center gap-1"><MapPin className="w-3 h-3" /> {event.location}</span>}
                        <span className="flex items-center gap-1">
                          <CalendarDays className="w-3 h-3" />
                          {new Date(event.start_date).toLocaleDateString("de-DE")} – {new Date(event.end_date).toLocaleDateString("de-DE")}
                        </span>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Step: Signup Details */}
          {step === "signup" && selectedEvent && (
            <div data-testid="signup-step">
              <button onClick={() => setStep("event")} className="flex items-center gap-1 text-sm text-gray-500 hover:text-fuchsia-600 mb-4">
                <ArrowLeft className="w-4 h-4" /> Zurück zur Auswahl
              </button>
              <div className="bg-white border border-gray-200 rounded-xl p-6 space-y-5">
                <div>
                  <h2 className="text-lg font-bold text-gray-900 mb-1">{selectedEvent.name}</h2>
                  <div className="flex flex-wrap gap-3 text-xs text-gray-500">
                    {selectedEvent.location && <span className="flex items-center gap-1"><MapPin className="w-3 h-3" /> {selectedEvent.location}</span>}
                    <span className="flex items-center gap-1">
                      <CalendarDays className="w-3 h-3" />
                      {new Date(selectedEvent.start_date).toLocaleDateString("de-DE")} – {new Date(selectedEvent.end_date).toLocaleDateString("de-DE")}
                    </span>
                  </div>
                </div>

                <div className="border-t border-gray-100 pt-4 space-y-4">
                  <div>
                    <Label className="text-gray-700 text-sm">Platznummer *</Label>
                    <Input value={signupForm.platznummer} onChange={e => setSignupForm(f => ({ ...f, platznummer: e.target.value }))} placeholder="z.B. A12" className="mt-1" data-testid="signup-platznummer" />
                  </div>
                  <div>
                    <Label className="text-gray-700 text-sm">Fahrgeschäft / Betrieb *</Label>
                    <Input value={signupForm.fahrgeschaeft} onChange={e => setSignupForm(f => ({ ...f, fahrgeschaeft: e.target.value }))} placeholder="z.B. Achterbahn, Autoscooter, Imbissbude" className="mt-1" data-testid="signup-fahrgeschaeft" />
                  </div>
                  <div>
                    <Label className="text-gray-700 text-sm">Stromanschluss *</Label>
                    <div className="grid grid-cols-3 sm:grid-cols-5 gap-2 mt-1">
                      {(selectedEvent.prices || []).map(p => (
                        <button
                          key={p.connection_type}
                          onClick={() => setSignupForm(f => ({ ...f, connection_type: p.connection_type }))}
                          className={`p-3 rounded-lg border text-center transition-colors ${
                            signupForm.connection_type === p.connection_type
                              ? "border-fuchsia-500 bg-fuchsia-50 text-fuchsia-700"
                              : "border-gray-200 text-gray-600 hover:border-gray-300"
                          }`}
                          data-testid={`conn-${p.connection_type}`}
                        >
                          <Zap className="w-4 h-4 mx-auto mb-1" />
                          <span className="text-xs font-medium block">{p.connection_type}</span>
                          <span className="text-[10px] text-gray-400 block">{p.price.toFixed(2)} EUR</span>
                        </button>
                      ))}
                    </div>
                  </div>
                  <div>
                    <Label className="text-gray-700 text-sm">Zahlungsmittel</Label>
                    <select
                      value={signupForm.payment_method}
                      onChange={e => setSignupForm(f => ({ ...f, payment_method: e.target.value }))}
                      className="w-full mt-1 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-fuchsia-500 bg-white"
                      data-testid="signup-payment"
                    >
                      {PAYMENT_METHODS.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
                    </select>
                  </div>

                  {getPrice() !== null && (
                    <div className="bg-fuchsia-50 border border-fuchsia-200 rounded-lg p-4">
                      <div className="flex justify-between items-center">
                        <span className="text-sm text-fuchsia-700 font-medium">Anschlussgebühr</span>
                        <span className="text-lg font-bold text-fuchsia-800">{getPrice().toFixed(2)} EUR</span>
                      </div>
                      <p className="text-[10px] text-fuchsia-500 mt-1">Die Sicherheitsleistung wird bei Bestätigung auf Ihrem Zahlungsmittel reserviert.</p>
                    </div>
                  )}
                </div>

                <Button onClick={handleSignup} disabled={saving} className="w-full bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="submit-signup-btn">
                  {saving ? "Wird angemeldet..." : "Verbindlich anmelden"} <ArrowRight className="w-4 h-4 ml-1" />
                </Button>
              </div>
            </div>
          )}

          {/* Step: Done */}
          {step === "done" && (
            <div className="bg-white border border-gray-200 rounded-xl p-8 text-center" data-testid="done-step">
              <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-emerald-100 flex items-center justify-center">
                <Check className="w-8 h-8 text-emerald-600" />
              </div>
              <h2 className="text-xl font-bold text-gray-900 mb-2">Anmeldung erfolgreich!</h2>
              <p className="text-sm text-gray-500 mb-4">
                Sie wurden für <strong>{selectedEvent?.name}</strong> angemeldet.
                Sie erhalten eine Bestätigung per E-Mail.
              </p>
              <div className="bg-gray-50 rounded-lg p-4 text-left text-sm space-y-1 mb-6">
                <p><span className="text-gray-500">Platz:</span> <strong>{signupForm.platznummer}</strong></p>
                <p><span className="text-gray-500">Fahrgeschäft:</span> <strong>{signupForm.fahrgeschaeft}</strong></p>
                <p><span className="text-gray-500">Anschluss:</span> <strong>{signupForm.connection_type}</strong></p>
                <p><span className="text-gray-500">Zahlung:</span> <strong className="capitalize">{signupForm.payment_method}</strong></p>
              </div>
              <Button variant="outline" onClick={() => { setStep("event"); setSignupForm({ platznummer: "", fahrgeschaeft: "", connection_type: "", payment_method: "kreditkarte" }); }} data-testid="another-event-btn">
                Für weitere Veranstaltung anmelden
              </Button>
            </div>
          )}
        </div>
      </main>

      <footer className="bg-white border-t border-gray-200 p-4 text-center text-sm text-gray-500">
        &copy; {new Date().getFullYear()} Eventenergie Deutschland GmbH & Co. KG
      </footer>
    </div>
  );
}
