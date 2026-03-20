import { useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Logo } from "../components/Logo";
import { toast } from "sonner";
import axios from "axios";
import { Mail, ArrowLeft, CheckCircle } from "lucide-react";
import { BACKEND_URL } from "../lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email) {
      toast.error("Bitte E-Mail eingeben");
      return;
    }

    setLoading(true);
    try {
      await axios.post(`${BACKEND_URL}/api/auth/request-password-reset`, {
        email,
        frontend_url: window.location.origin,
      });
      setSent(true);
      toast.success("Falls die E-Mail existiert, wurde ein Link gesendet");
    } catch {
      toast.error("Fehler beim Senden");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-white flex flex-col" data-testid="forgot-password-page">
      <header className="p-6 flex justify-center">
        <Logo size="large" />
      </header>

      <main className="flex-1 flex items-center justify-center px-4 pb-12">
        <div className="w-full max-w-md">
          <div className="bg-white border border-gray-200 rounded-lg shadow-lg p-8 space-y-6">
            {sent ? (
              <div className="text-center space-y-4">
                <div className="w-16 h-16 rounded-full bg-green-100 flex items-center justify-center mx-auto">
                  <CheckCircle className="w-8 h-8 text-green-500" />
                </div>
                <h1 className="text-2xl font-bold text-gray-900">E-Mail gesendet</h1>
                <p className="text-gray-500">
                  Falls ein Konto mit dieser E-Mail existiert, wurde ein Link zum Zurücksetzen an <strong>{email}</strong> gesendet.
                </p>
                <p className="text-sm text-gray-400">
                  Bitte prüfen Sie auch Ihren Spam-Ordner.
                </p>
              </div>
            ) : (
              <>
                <div className="text-center">
                  <h1 className="text-2xl font-bold text-gray-900">Passwort vergessen?</h1>
                  <p className="text-gray-500 mt-1">
                    Geben Sie Ihre E-Mail-Adresse ein und wir senden Ihnen einen Link zum Zurücksetzen.
                  </p>
                </div>

                <form onSubmit={handleSubmit} className="space-y-4">
                  <div className="space-y-2">
                    <Label className="text-gray-700">E-Mail</Label>
                    <div className="relative">
                      <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                      <Input
                        type="email"
                        placeholder="name@firma.de"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        className="pl-10 h-12 bg-gray-50 border-gray-300"
                        data-testid="reset-email-input"
                      />
                    </div>
                  </div>

                  <Button
                    type="submit"
                    disabled={loading}
                    className="w-full h-12 bg-fuchsia-600 hover:bg-fuchsia-700 text-white font-semibold"
                    data-testid="send-reset-btn"
                  >
                    {loading ? "Wird gesendet..." : "Link senden"}
                  </Button>
                </form>
              </>
            )}

            <Link 
              to="/login" 
              className="flex items-center justify-center gap-2 text-gray-600 hover:text-fuchsia-600 transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
              Zurück zur Anmeldung
            </Link>
          </div>
        </div>
      </main>

      <footer className="p-6 text-center text-sm text-gray-500">
        &copy; {new Date().getFullYear()} Eventenergie Deutschland GmbH & Co. KG
      </footer>
    </div>
  );
}
