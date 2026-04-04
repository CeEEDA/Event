import { useState, useEffect, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import { Logo } from "../components/Logo";
import { toast } from "sonner";
import { LogOut } from "lucide-react";
import { BACKEND_URL, api, isPasswordValid } from "./schausteller/constants";
import { AuthStep } from "./schausteller/AuthStep";
import { VerifyStep } from "./schausteller/VerifyStep";
import { SetPasswordStep } from "./schausteller/SetPasswordStep";
import { ResetRequestStep, ResetConfirmStep } from "./schausteller/PasswordResetSteps";
import { Dashboard } from "./schausteller/Dashboard";
import { EventSelector } from "./schausteller/EventSelector";
import { SignupForm } from "./schausteller/SignupForm";
import { PaymentStep } from "./schausteller/PaymentStep";
import { PaymentCheckStep } from "./schausteller/PaymentCheckStep";
import { DoneStep } from "./schausteller/DoneStep";
import { AgbModal } from "./schausteller/AgbModal";
import { DatenschutzModal } from "./schausteller/DatenschutzModal";
import { ImpressumModal } from "./schausteller/ImpressumModal";

export default function SchaustellerAnmeldungPage() {
  const [searchParams] = useSearchParams();
  const preselectedEvent = searchParams.get("event");
  const verifiedParam = searchParams.get("verified");
  const verifiedEmail = searchParams.get("email");

  const [step, setStep] = useState("auth");
  const [showImpressum, setShowImpressum] = useState(false);
  const [showDatenschutz, setShowDatenschutz] = useState(false);
  const [showAgb, setShowAgb] = useState(false);
  const [agbAccepted, setAgbAccepted] = useState(false);
  const [schausteller, setSchausteller] = useState(null);
  const [events, setEvents] = useState([]);
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [saving, setSaving] = useState(false);
  const [myBookings, setMyBookings] = useState({ signups: [], invoices: [] });
  const [lastdiagramme, setLastdiagramme] = useState({ available: [], purchased: [] });
  const [ldPurchasing, setLdPurchasing] = useState(null);
  const [ldDownloading, setLdDownloading] = useState(null);
  const [verifyEmail2, setVerifyEmail2] = useState("");
  const [resetEmail, setResetEmail] = useState("");
  const [signupForm, setSignupForm] = useState({ platznummer: "", fahrgeschaeft: "", connection_type: "", payment_method: "kreditkarte" });
  const [additionalSignups, setAdditionalSignups] = useState([]);
  const [lastSignupId, setLastSignupId] = useState(null);
  const [completedBookings, setCompletedBookings] = useState([]);
  const [depositAmounts, setDepositAmounts] = useState({});
  const [paymentChecking, setPaymentChecking] = useState(false);

  const loadBookings = useCallback(async (schId) => {
    try { const r = await api.get(`/kirmes/public/my-bookings?schausteller_id=${schId}`); setMyBookings(r.data); } catch { /* ignore */ }
  }, []);

  const loadLastdiagramme = useCallback(async (schId) => {
    try { const r = await api.get(`/kirmes/public/lastdiagramm/available?schausteller_id=${schId}`); setLastdiagramme(r.data); } catch { /* ignore */ }
  }, []);

  const loadEvents = useCallback(async () => {
    try {
      const r = await api.get("/kirmes/public/events");
      setEvents(r.data);
      if (preselectedEvent) {
        const found = r.data.find(e => e.id === preselectedEvent);
        if (found) setSelectedEvent(found);
      }
    } catch { /* ignore */ }
  }, [preselectedEvent]);

  useEffect(() => { loadEvents(); }, [loadEvents]);

  const goToDashboard = useCallback((sch) => {
    setSchausteller(sch);
    loadBookings(sch.id);
    loadLastdiagramme(sch.id);
    if (preselectedEvent && selectedEvent) { setStep("signup"); }
    else { setStep("dashboard"); }
  }, [preselectedEvent, selectedEvent, loadBookings, loadLastdiagramme]);

  // Auto-verify from email link
  useEffect(() => {
    if (verifiedParam === "1" && verifiedEmail) {
      setVerifyEmail2(verifiedEmail);
      toast.success("E-Mail erfolgreich bestätigt!");
      (async () => {
        try {
          const r = await api.post("/kirmes/public/verify-email", { email: verifiedEmail, code: "already-verified" });
          if (r.data?.password_hash !== undefined || r.data?.email_verified) {
            goToDashboard(r.data);
          }
        } catch {
          setStep("setpw");
        }
      })();
    }
  }, [verifiedParam, verifiedEmail]); // eslint-disable-line react-hooks/exhaustive-deps

  // Stripe return
  const pollPaymentStatus = useCallback(async (sessionId, attempts = 0) => {
    if (attempts >= 10) { setPaymentChecking(false); return; }
    try {
      const r = await api.get(`/payments/checkout/status/${sessionId}`);
      if (r.data?.payment_status === "paid") {
        toast.success("Kaution erfolgreich bezahlt!");
        setPaymentChecking(false);
        setStep("done");
        if (schausteller) { loadBookings(schausteller.id); loadLastdiagramme(schausteller.id); }
        return;
      }
      if (r.data?.status === "expired") {
        toast.error("Zahlungssitzung abgelaufen");
        setPaymentChecking(false);
        setStep("done");
        return;
      }
    } catch { /* ignore */ }
    setTimeout(() => pollPaymentStatus(sessionId, attempts + 1), 2000);
  }, [schausteller, loadBookings, loadLastdiagramme]);

  useEffect(() => {
    const sessionId = searchParams.get("session_id");
    const paymentResult = searchParams.get("payment");
    if (sessionId && paymentResult === "success") {
      setPaymentChecking(true);
      setStep("payment_check");
      pollPaymentStatus(sessionId);
    } else if (paymentResult === "cancelled") {
      toast.error("Zahlung abgebrochen");
    }
  }, [searchParams, pollPaymentStatus]);

  // Load deposit amounts when event is selected
  useEffect(() => {
    if (selectedEvent) {
      api.get(`/payments/deposit-info/${selectedEvent.id}`)
        .then(r => setDepositAmounts(r.data))
        .catch(() => {});
    }
  }, [selectedEvent]);

  // --- Handlers ---
  const handleLogin = async (email, password) => {
    if (!email || !password) { toast.error("Bitte E-Mail und Passwort eingeben"); return; }
    setSaving(true);
    try {
      const r = await api.post("/kirmes/public/login", { email, password });
      toast.success(`Willkommen zurück, ${r.data.name}!`);
      goToDashboard(r.data);
    } catch (err) {
      toast.error(typeof (err?.response?.data?.detail) === "string" ? err.response.data.detail : "Fehler bei der Anmeldung");
    } finally { setSaving(false); }
  };

  const handleRegister = async (regForm) => {
    if (!regForm.name || !regForm.email) { toast.error("Bitte Name und E-Mail eingeben"); return; }
    setSaving(true);
    try {
      await api.post("/kirmes/public/register", regForm);
      setVerifyEmail2(regForm.email);
      toast.success("Bestätigungscode wurde an Ihre E-Mail gesendet!");
      setStep("verify");
    } catch (err) {
      toast.error(typeof (err?.response?.data?.detail) === "string" ? err.response.data.detail : "Fehler bei der Registrierung");
    } finally { setSaving(false); }
  };

  const handleVerify = async (code) => {
    if (!code || code.length !== 6) { toast.error("Bitte den 6-stelligen Code eingeben"); return; }
    setSaving(true);
    try {
      const r = await api.post("/kirmes/public/verify-email", { email: verifyEmail2, code });
      toast.success("E-Mail bestätigt! Bitte setzen Sie jetzt Ihr Passwort.");
      setSchausteller(r.data);
      setStep("setpw");
    } catch (err) {
      toast.error(typeof (err?.response?.data?.detail) === "string" ? err.response.data.detail : "Ungültiger Code");
    } finally { setSaving(false); }
  };

  const handleResendCode = async () => {
    try { await api.get(`/kirmes/public/resend-code?email=${encodeURIComponent(verifyEmail2)}`); toast.success("Neuer Code wurde gesendet"); }
    catch (err) { toast.error(typeof (err?.response?.data?.detail) === "string" ? err.response.data.detail : "Fehler"); }
  };

  const handleSetPassword = async (pw, pwConfirm) => {
    if (!isPasswordValid(pw)) { toast.error("Passwort erfüllt nicht alle Anforderungen"); return; }
    if (pw !== pwConfirm) { toast.error("Passwörter stimmen nicht überein"); return; }
    setSaving(true);
    try {
      const r = await api.post("/kirmes/public/set-password", { email: verifyEmail2, password: pw });
      toast.success("Passwort gesetzt!");
      goToDashboard(r.data);
    } catch (err) {
      toast.error(typeof (err?.response?.data?.detail) === "string" ? err.response.data.detail : "Fehler");
    } finally { setSaving(false); }
  };

  const handleForgotPassword = (email) => { setResetEmail(email); setStep("reset-request"); };

  const handleResetSendCode = async (email) => {
    if (!email) { toast.error("Bitte E-Mail eingeben"); return; }
    setSaving(true);
    try {
      await api.post("/kirmes/public/request-password-reset", { email });
      setResetEmail(email);
      toast.success("Code wurde gesendet!");
      setStep("reset-confirm");
    } catch (err) {
      toast.error(typeof (err?.response?.data?.detail) === "string" ? err.response.data.detail : "Fehler");
    } finally { setSaving(false); }
  };

  const handleResetConfirm = async (email, code, pw, pwConfirm) => {
    if (!code || code.length < 6) { toast.error("Bitte 6-stelligen Code eingeben"); return; }
    if (!isPasswordValid(pw)) { toast.error("Passwort erfüllt nicht alle Anforderungen"); return; }
    if (pw !== pwConfirm) { toast.error("Passwörter stimmen nicht überein"); return; }
    setSaving(true);
    try {
      const r = await api.post("/kirmes/public/confirm-password-reset", { email, code, password: pw });
      toast.success("Passwort erfolgreich geändert!");
      goToDashboard(r.data);
    } catch (err) {
      toast.error(typeof (err?.response?.data?.detail) === "string" ? err.response.data.detail : "Fehler");
    } finally { setSaving(false); }
  };

  const handleSignup = async () => {
    if (!signupForm.platznummer || !signupForm.fahrgeschaeft || !signupForm.connection_type) {
      toast.error("Bitte Platznummer, Fahrgeschäft und Anschluss angeben"); return;
    }
    for (let i = 0; i < additionalSignups.length; i++) {
      const a = additionalSignups[i];
      if (a.isWohnwagen) {
        if (!a.platznummer || !a.connection_type) { toast.error(`Bitte Platznummer und Anschluss beim Wohnwagen ${i + 1} ausfüllen`); return; }
      } else {
        if (!a.platznummer || !a.fahrgeschaeft || !a.connection_type) { toast.error(`Bitte alle Felder beim ${i + 2}. Anschluss ausfüllen`); return; }
      }
    }
    setSaving(true);
    try {
      const regularPrices = selectedEvent.prices || [];
      const wwPrices = selectedEvent.wohnwagen_prices || [];
      const isRechnung = signupForm.payment_method === "rechnung";
      const summaryItems = [];
      const mainP = regularPrices.find(p => p.connection_type === signupForm.connection_type);
      summaryItems.push({ platznummer: signupForm.platznummer, fahrgeschaeft: signupForm.fahrgeschaeft, connection_type: signupForm.connection_type, price: mainP?.price || 0, deposit: (!isRechnung && depositAmounts[signupForm.connection_type]) || 0 });
      for (const extra of additionalSignups) {
        const priceList = extra.isWohnwagen ? wwPrices : regularPrices;
        const p = priceList.find(pr => pr.connection_type === extra.connection_type);
        summaryItems.push({ platznummer: extra.platznummer, fahrgeschaeft: extra.isWohnwagen ? "Wohnwagen" : extra.fahrgeschaeft, connection_type: extra.connection_type, price: p?.price || 0, deposit: (!isRechnung && !extra.isWohnwagen && depositAmounts[extra.connection_type]) || 0 });
      }
      setCompletedBookings(summaryItems);

      const r = await api.post("/kirmes/public/signup", { event_id: selectedEvent.id, schausteller_id: schausteller.id, ...signupForm });
      const signupId = r.data?.signup_id || r.data?.id;
      setLastSignupId(signupId);

      for (const extra of additionalSignups) {
        await api.post("/kirmes/public/signup", { event_id: selectedEvent.id, schausteller_id: schausteller.id, ...extra, payment_method: signupForm.payment_method });
      }

      if (r.data?.payment_status === "pending_payment") {
        toast.success(`${1 + additionalSignups.length} Anmeldung(en) vorgemerkt! Bitte bezahlen Sie die Kaution.`);
        setStep("payment");
      } else {
        toast.success(`${1 + additionalSignups.length} Anmeldung(en) erfolgreich!`);
        setStep("done");
      }
      setAdditionalSignups([]);
    } catch (err) {
      toast.error(typeof (err?.response?.data?.detail) === "string" ? err.response.data.detail : "Fehler bei der Anmeldung");
    } finally { setSaving(false); }
  };

  const handlePayDeposit = async () => {
    if (!lastSignupId || !selectedEvent) return;
    setSaving(true);
    try {
      const r = await api.post("/payments/checkout/deposit", { signup_id: lastSignupId, event_id: selectedEvent.id, origin_url: window.location.origin });
      if (r.data?.url) { window.location.href = r.data.url; }
    } catch (err) {
      toast.error(typeof (err?.response?.data?.detail) === "string" ? err.response.data.detail : "Fehler bei der Zahlung");
    } finally { setSaving(false); }
  };

  const handleDownloadInvoice = async (invoiceId) => {
    try {
      const response = await fetch(`${BACKEND_URL}/api/kirmes/public/invoice/${invoiceId}/pdf?schausteller_id=${schausteller.id}`);
      if (!response.ok) throw new Error();
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a"); a.href = url; a.download = "Rechnung.pdf"; a.click();
      window.URL.revokeObjectURL(url);
    } catch { toast.error("PDF konnte nicht heruntergeladen werden"); }
  };

  const purchaseLastdiagramm = async (signupId) => {
    if (!schausteller) return;
    setLdPurchasing(signupId);
    try {
      const payMethod = schausteller.kauf_auf_rechnung ? "rechnung" : "kreditkarte";
      const r = await api.post("/kirmes/public/lastdiagramm/purchase", { schausteller_id: schausteller.id, signup_id: signupId, payment_method: payMethod });
      toast.success(`Lastdiagramm bestellt! Rechnung: ${r.data.invoice?.invoice_number}`);
      loadLastdiagramme(schausteller.id);
      loadBookings(schausteller.id);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Fehler beim Bestellen");
    } finally { setLdPurchasing(null); }
  };

  const downloadLastdiagramm = async (orderId) => {
    if (!schausteller) return;
    setLdDownloading(orderId);
    try {
      const resp = await fetch(`${BACKEND_URL}/api/kirmes/public/lastdiagramm/${orderId}/pdf?schausteller_id=${schausteller.id}`);
      if (!resp.ok) { const d = await resp.json(); throw { response: { data: d } }; }
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a"); a.href = url; a.download = "Lastdiagramm.pdf"; a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Fehler beim Download");
    } finally { setLdDownloading(null); }
  };

  const handlePurchaseLastdiagramm = (signupId, eventName, kaufAufRechnung) => {
    if (window.confirm(`Lastdiagramm für "${eventName}" kaufen?\n\n125,00 EUR zzgl. MwSt.\n= 148,75 EUR brutto\n\nZahlung: ${kaufAufRechnung ? "Auf Rechnung" : "Kreditkarte / PayPal"}`)) {
      purchaseLastdiagramm(signupId);
    }
  };

  const handleLogout = () => { setSchausteller(null); setMyBookings({ signups: [], invoices: [] }); setStep("auth"); };

  const resetSignupForm = () => { setSignupForm({ platznummer: "", fahrgeschaeft: "", connection_type: "", payment_method: "kreditkarte" }); setAdditionalSignups([]); setCompletedBookings([]); };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col" data-testid="schausteller-anmeldung">
      <header className="bg-white border-b border-gray-200 p-4">
        <div className="max-w-lg mx-auto flex items-center justify-between">
          <Logo size="normal" />
          <div className="flex items-center gap-3">
            {schausteller && step !== "auth" && step !== "verify" && step !== "setpw" && (
              <>
                <span className="text-xs text-gray-500 hidden sm:inline">{schausteller.name}</span>
                <button onClick={handleLogout} className="text-gray-400 hover:text-gray-600" title="Abmelden" data-testid="logout-btn"><LogOut className="w-4 h-4" /></button>
              </>
            )}
            <p className="text-xs text-gray-400">Schausteller-Portal</p>
          </div>
        </div>
      </header>

      <main className="flex-1 flex items-start justify-center p-4 pt-8">
        <div className="w-full max-w-lg">
          {step === "auth" && (
            <AuthStep onLogin={handleLogin} onRegister={handleRegister} onForgotPassword={handleForgotPassword} saving={saving} />
          )}
          {step === "verify" && (
            <VerifyStep email={verifyEmail2} onVerify={handleVerify} onResend={handleResendCode} saving={saving} />
          )}
          {step === "setpw" && (
            <SetPasswordStep onSetPassword={handleSetPassword} saving={saving} />
          )}
          {step === "reset-request" && (
            <ResetRequestStep onSendCode={handleResetSendCode} onBack={() => setStep("auth")} saving={saving} initialEmail={resetEmail} />
          )}
          {step === "reset-confirm" && (
            <ResetConfirmStep email={resetEmail} onConfirm={handleResetConfirm} onBack={() => setStep("auth")} saving={saving} />
          )}
          {step === "dashboard" && schausteller && (
            <Dashboard
              schausteller={schausteller}
              myBookings={myBookings}
              lastdiagramme={lastdiagramme}
              onNewBooking={() => { loadEvents(); setStep("event"); }}
              onDownloadInvoice={handleDownloadInvoice}
              onPurchaseLastdiagramm={handlePurchaseLastdiagramm}
              onDownloadLastdiagramm={downloadLastdiagramm}
              ldPurchasing={ldPurchasing}
              ldDownloading={ldDownloading}
            />
          )}
          {step === "event" && (
            <EventSelector
              events={events}
              onSelect={(event) => { setSelectedEvent(event); setStep("signup"); }}
              onBack={() => { loadBookings(schausteller.id); loadLastdiagramme(schausteller.id); setStep("dashboard"); }}
            />
          )}
          {step === "signup" && selectedEvent && (
            <SignupForm
              selectedEvent={selectedEvent}
              signupForm={signupForm}
              setSignupForm={setSignupForm}
              additionalSignups={additionalSignups}
              setAdditionalSignups={setAdditionalSignups}
              depositAmounts={depositAmounts}
              schausteller={schausteller}
              agbAccepted={agbAccepted}
              setAgbAccepted={setAgbAccepted}
              setShowAgb={setShowAgb}
              onSubmit={handleSignup}
              onBack={() => setStep("event")}
              saving={saving}
            />
          )}
          {step === "payment" && (
            <PaymentStep
              selectedEvent={selectedEvent}
              signupForm={signupForm}
              depositAmounts={depositAmounts}
              onPayDeposit={handlePayDeposit}
              onSkip={() => { loadBookings(schausteller.id); setStep("dashboard"); resetSignupForm(); }}
              saving={saving}
            />
          )}
          {step === "payment_check" && (
            <PaymentCheckStep paymentChecking={paymentChecking} />
          )}
          {step === "done" && (
            <DoneStep
              selectedEvent={selectedEvent}
              completedBookings={completedBookings}
              signupForm={signupForm}
              onAnotherSignup={() => { resetSignupForm(); setStep("signup"); }}
              onToDashboard={() => { loadBookings(schausteller.id); setStep("dashboard"); resetSignupForm(); }}
            />
          )}
        </div>
      </main>

      <footer className="bg-white border-t border-gray-200 p-4 text-center text-sm text-gray-500">
        <span>&copy; {new Date().getFullYear()} Eventenergie Deutschland GmbH & Co. KG</span>
        <span className="mx-2">&middot;</span>
        <button onClick={() => setShowDatenschutz(true)} className="text-fuchsia-600 hover:text-fuchsia-700 underline" data-testid="datenschutz-btn">Datenschutz</button>
        <span className="mx-2">&middot;</span>
        <button onClick={() => setShowImpressum(true)} className="text-fuchsia-600 hover:text-fuchsia-700 underline" data-testid="impressum-btn">Impressum</button>
      </footer>

      <AgbModal show={showAgb} onClose={() => setShowAgb(false)} />
      <DatenschutzModal show={showDatenschutz} onClose={() => setShowDatenschutz(false)} />
      <ImpressumModal show={showImpressum} onClose={() => setShowImpressum(false)} />
    </div>
  );
}
