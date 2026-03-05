import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { toast } from "sonner";
import { Lock, Mail, ArrowRight, Zap } from "lucide-react";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email || !password) {
      toast.error("Bitte alle Felder ausfüllen");
      return;
    }

    setLoading(true);
    try {
      await login(email, password);
      toast.success("Erfolgreich angemeldet");
    } catch (error) {
      const message = error.response?.data?.detail || "Anmeldung fehlgeschlagen";
      toast.error(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 h-screen w-full" data-testid="login-page">
      {/* Left Panel - Branding */}
      <div className="hidden lg:flex flex-col justify-between p-12 bg-card relative overflow-hidden">
        {/* Background Pattern */}
        <div className="absolute inset-0 grid-lines opacity-50" />
        <div 
          className="absolute inset-0 opacity-20"
          style={{
            backgroundImage: `url('https://images.unsplash.com/photo-1597947414275-c0d307e3e12e?w=1200&q=80')`,
            backgroundSize: 'cover',
            backgroundPosition: 'center',
          }}
        />
        <div className="absolute inset-0 bg-gradient-to-br from-background/90 via-background/70 to-transparent" />
        
        {/* Content */}
        <div className="relative z-10">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-sm bg-primary flex items-center justify-center glow-orange">
              <Zap className="w-6 h-6 text-primary-foreground" />
            </div>
            <span className="text-2xl font-bold tracking-tight">FileShare</span>
          </div>
          <p className="text-muted-foreground text-sm">Eventenergie Deutschland</p>
        </div>
        
        <div className="relative z-10 space-y-6">
          <h1 className="text-4xl lg:text-5xl font-bold tracking-tight leading-tight">
            Sichere<br />
            <span className="text-gradient">Dateifreigabe</span><br />
            für Ihr Business
          </h1>
          <p className="text-muted-foreground text-lg max-w-md">
            Teilen Sie Dateien sicher mit Kunden und Mitarbeitern. 
            Volle Kontrolle über Zugriffsrechte und Ablaufdaten.
          </p>
        </div>
        
        <div className="relative z-10 text-sm text-muted-foreground">
          &copy; {new Date().getFullYear()} Eventenergie Deutschland GmbH & Co. KG
        </div>
      </div>

      {/* Right Panel - Login Form */}
      <div className="flex items-center justify-center p-8 bg-background">
        <div className="w-full max-w-md space-y-8 animate-fade-in">
          {/* Mobile Logo */}
          <div className="lg:hidden flex items-center gap-3 justify-center mb-8">
            <div className="w-10 h-10 rounded-sm bg-primary flex items-center justify-center">
              <Zap className="w-6 h-6 text-primary-foreground" />
            </div>
            <span className="text-2xl font-bold tracking-tight">FileShare</span>
          </div>

          <div className="space-y-2 text-center lg:text-left">
            <h2 className="text-3xl font-bold tracking-tight">Anmelden</h2>
            <p className="text-muted-foreground">
              Geben Sie Ihre Zugangsdaten ein
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="email" className="text-sm font-medium uppercase tracking-wide">
                  E-Mail
                </Label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                  <Input
                    id="email"
                    type="email"
                    placeholder="name@firma.de"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="pl-10 h-12 bg-card border-border focus:border-primary transition-colors"
                    data-testid="login-email-input"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="password" className="text-sm font-medium uppercase tracking-wide">
                  Passwort
                </Label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                  <Input
                    id="password"
                    type="password"
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="pl-10 h-12 bg-card border-border focus:border-primary transition-colors"
                    data-testid="login-password-input"
                  />
                </div>
              </div>
            </div>

            <Button
              type="submit"
              disabled={loading}
              className="w-full h-12 bg-primary hover:bg-primary/90 text-primary-foreground font-semibold uppercase tracking-wide glow-orange transition-all active:scale-[0.98]"
              data-testid="login-submit-btn"
            >
              {loading ? (
                "Wird angemeldet..."
              ) : (
                <>
                  Anmelden
                  <ArrowRight className="ml-2 w-5 h-5" />
                </>
              )}
            </Button>
          </form>

          <div className="text-center text-sm text-muted-foreground">
            Noch kein Konto?{" "}
            <Link 
              to="/register" 
              className="text-primary hover:underline font-medium"
              data-testid="register-link"
            >
              Registrieren
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
