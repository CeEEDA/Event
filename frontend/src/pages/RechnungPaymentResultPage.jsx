import { useEffect, useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { CheckCircle2, XCircle, Loader2 } from "lucide-react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;

export function RechnungBezahltPage() {
  const [params] = useSearchParams();
  const [status, setStatus] = useState("checking"); // checking | paid | pending | error
  const sessionId = params.get("session_id");

  useEffect(() => {
    if (!sessionId) {
      setStatus("error");
      return;
    }
    let cancelled = false;
    let attempts = 0;
    const poll = async () => {
      try {
        const res = await axios.get(`${API}/api/payments/checkout/status/${sessionId}`);
        const s = res.data?.payment_status || res.data?.status;
        if (cancelled) return;
        if (s === "paid") {
          setStatus("paid");
          return;
        }
        attempts += 1;
        if (attempts < 10) {
          setTimeout(poll, 2000);
        } else {
          setStatus("pending");
        }
      } catch (e) {
        if (!cancelled) setStatus("pending");
      }
    };
    poll();
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex items-center justify-center p-6">
      <div className="bg-white rounded-2xl shadow-xl max-w-md w-full p-10 text-center" data-testid="rechnung-bezahlt-page">
        {status === "checking" && (
          <>
            <Loader2 className="h-16 w-16 text-fuchsia-500 mx-auto mb-4 animate-spin" />
            <h1 className="text-2xl font-semibold text-slate-800 mb-2">Zahlung wird verarbeitet</h1>
            <p className="text-slate-500 text-sm">Bitte einen Moment Geduld ...</p>
          </>
        )}
        {status === "paid" && (
          <>
            <CheckCircle2 className="h-16 w-16 text-emerald-500 mx-auto mb-4" data-testid="payment-success-icon" />
            <h1 className="text-2xl font-semibold text-slate-800 mb-2">Vielen Dank!</h1>
            <p className="text-slate-500 text-sm mb-4">Ihre Zahlung ist bei uns eingegangen. Sie erhalten in Kürze eine Bestätigung per E-Mail.</p>
          </>
        )}
        {status === "pending" && (
          <>
            <Loader2 className="h-16 w-16 text-amber-500 mx-auto mb-4" />
            <h1 className="text-2xl font-semibold text-slate-800 mb-2">Zahlung eingeleitet</h1>
            <p className="text-slate-500 text-sm">Ihre Zahlung wurde eingeleitet und wird in Kürze bestätigt. Sie können dieses Fenster schließen.</p>
          </>
        )}
        {status === "error" && (
          <>
            <XCircle className="h-16 w-16 text-red-500 mx-auto mb-4" />
            <h1 className="text-2xl font-semibold text-slate-800 mb-2">Session nicht gefunden</h1>
            <p className="text-slate-500 text-sm">Der Zahlungsvorgang konnte nicht überprüft werden. Bitte kontaktieren Sie uns, falls Sie unsicher sind.</p>
          </>
        )}
      </div>
    </div>
  );
}

export function RechnungAbgebrochenPage() {
  const navigate = useNavigate();
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex items-center justify-center p-6">
      <div className="bg-white rounded-2xl shadow-xl max-w-md w-full p-10 text-center" data-testid="rechnung-abgebrochen-page">
        <XCircle className="h-16 w-16 text-amber-500 mx-auto mb-4" />
        <h1 className="text-2xl font-semibold text-slate-800 mb-2">Zahlung abgebrochen</h1>
        <p className="text-slate-500 text-sm mb-6">Sie haben den Bezahlvorgang abgebrochen. Sie können die Rechnung jederzeit später begleichen — der Link in der E-Mail bleibt gültig.</p>
        <button
          onClick={() => navigate("/login")}
          className="px-6 py-2 bg-fuchsia-500 text-white rounded-lg hover:bg-fuchsia-600 transition"
          data-testid="rechnung-abgebrochen-back-btn"
        >
          Zur Startseite
        </button>
      </div>
    </div>
  );
}
