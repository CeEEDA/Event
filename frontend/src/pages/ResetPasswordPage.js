import { useState, useEffect } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Logo } from "../components/Logo";
import { toast } from "sonner";
import axios from "axios";
import { Lock, ArrowLeft, CheckCircle, AlertCircle } from "lucide-react";
import { BACKEND_URL } from "../lib/api";

export default function ResetPasswordPage() {
  const { token } = useParams();
  const navigate = useNavigate();
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [verifying, setVerifying] = useState(true);
  const [tokenValid, setTokenValid] = useState(false);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    const verifyToken = async () => {
      try {
        await axios.get(`${BACKEND_URL}/api/auth/verify-reset-token/${token}`);
        setTokenValid(true);
      } catch (error) {
        setTokenValid(false);
      } finally {
        setVerifying(false);
      }
    };

    if (token) {
      verifyToken();
    } else {
      setVerifying(false);
    }
  }, [token]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (newPassword !== confirmPassword) {
      toast.error("Passwörter stimmen nicht überein");
      return;
    }

    if (newPassword.length < 6) {
      toast.error("Passwort muss mindestens 6 Zeichen haben");
      return;
    }

    setLoading(true);
    try {
      await axios.post(`${BACKEND_URL}/api/auth/reset-password`, {
        token,
        new_password: newPassword
      });
      setSuccess(true);
      toast.success("Passwort erfolgreich geändert");
    } catch (error) {
      const message = error.response?.data?.detail || "Fehler beim Zurücksetzen";
      toast.error(message);
    } finally {
      setLoading(false);
    }
  };

  if (verifying) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center">
        <div className="animate-pulse text-fuchsia-600">Wird überprüft...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-white flex flex-col" data-testid="reset-password-page">
      <header className="p-6 flex justify-center">
        <Logo size="large" />
      </header>

      <main className="flex-1 flex items-center justify-center px-4 pb-12">
        <div className="w-full max-w-md">
          <div className="bg-white border border-gray-200 rounded-lg shadow-lg p-8 space-y-6">
            {success ? (
              <div className="text-center space-y-4">
                <div className="w-16 h-16 rounded-full bg-green-100 flex items-center justify-center mx-auto">
                  <CheckCircle className="w-8 h-8 text-green-500" />
                </div>
                <h1 className="text-2xl font-bold text-gray-900">Passwort geändert</h1>
                <p className="text-gray-500">
                  Ihr Passwort wurde erfolgreich geändert. Sie können sich jetzt anmelden.
                </p>
                <Button
                  onClick={() => navigate("/login")}
                  className="w-full bg-fuchsia-600 hover:bg-fuchsia-700 text-white"
                >
                  Zur Anmeldung
                </Button>
              </div>
            ) : !tokenValid ? (
              <div className="text-center space-y-4">
                <div className="w-16 h-16 rounded-full bg-red-100 flex items-center justify-center mx-auto">
                  <AlertCircle className="w-8 h-8 text-red-500" />
                </div>
                <h1 className="text-2xl font-bold text-gray-900">Link ungültig</h1>
                <p className="text-gray-500">
                  Dieser Link ist ungültig oder abgelaufen. Bitte fordern Sie einen neuen Link an.
                </p>
                <Link to="/forgot-password">
                  <Button variant="outline" className="w-full border-gray-300">
                    Neuen Link anfordern
                  </Button>
                </Link>
              </div>
            ) : (
              <>
                <div className="text-center">
                  <h1 className="text-2xl font-bold text-gray-900">Neues Passwort</h1>
                  <p className="text-gray-500 mt-1">
                    Geben Sie Ihr neues Passwort ein
                  </p>
                </div>

                <form onSubmit={handleSubmit} className="space-y-4">
                  <div className="space-y-2">
                    <Label className="text-gray-700">Neues Passwort</Label>
                    <div className="relative">
                      <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                      <Input
                        type="password"
                        placeholder="Mindestens 6 Zeichen"
                        value={newPassword}
                        onChange={(e) => setNewPassword(e.target.value)}
                        className="pl-10 h-12 bg-gray-50 border-gray-300"
                        data-testid="new-password-input"
                      />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label className="text-gray-700">Passwort bestätigen</Label>
                    <div className="relative">
                      <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                      <Input
                        type="password"
                        placeholder="Passwort wiederholen"
                        value={confirmPassword}
                        onChange={(e) => setConfirmPassword(e.target.value)}
                        className="pl-10 h-12 bg-gray-50 border-gray-300"
                        data-testid="confirm-password-input"
                      />
                    </div>
                  </div>

                  <Button
                    type="submit"
                    disabled={loading}
                    className="w-full h-12 bg-fuchsia-600 hover:bg-fuchsia-700 text-white font-semibold"
                    data-testid="reset-submit-btn"
                  >
                    {loading ? "Wird gespeichert..." : "Passwort speichern"}
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
