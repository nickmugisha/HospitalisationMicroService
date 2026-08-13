import {
  Eye,
  EyeOff,
  HeartPulse,
  LockKeyhole,
  UserRound,
} from "lucide-react";
import {
  useState,
  type FormEvent,
} from "react";
import {
  Navigate,
  useNavigate,
} from "react-router-dom";

import { useAuth } from "../auth/AuthContext";

export default function LoginPage() {
  const navigate = useNavigate();
  const {
    login,
    isAuthenticated,
  } = useAuth();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] =
    useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] =
    useState(false);

  if (isAuthenticated) {
    return (
      <Navigate
        to="/"
        replace
      />
    );
  }

  async function handleSubmit(
    event: FormEvent<HTMLFormElement>
  ) {
    event.preventDefault();

    setError("");
    setLoading(true);

    await new Promise((resolve) =>
      setTimeout(resolve, 500)
    );

    const authenticatedUser =
      await login(
        username,
        password
      );

    setLoading(false);

    if (!authenticatedUser) {
      setError(
        "Identifiant ou mot de passe incorrect."
      );

      return;
    }

    navigate("/");
  }

  return (
    <div className="login-page">
      <section className="login-brand-panel">
        <div className="login-brand-content">
          <div className="login-big-logo">
            <HeartPulse size={42} />
          </div>

          <p className="login-kicker">
            PLATEFORME HOSPITALIÈRE DISTRIBUÉE
          </p>

          <h1>
            HOSPITALIS
            <span>MicroServices</span>
          </h1>

          <p className="login-description">
            Une plateforme unifiée pour le parcours
            patient, les soins, le laboratoire,
            la pharmacie, l'hospitalisation et
            la gestion hospitalière.
          </p>

          <div className="login-tech">
            <span>React</span>
            <span>FastAPI</span>
            <span>gRPC</span>
            <span>Microservices</span>
          </div>
        </div>

        <div className="login-network">
          Client Linux
          <span>→</span>
          Serveur Windows
        </div>
      </section>

      <section className="login-form-panel">
        <form
          className="login-form"
          onSubmit={handleSubmit}
        >
          <div className="mobile-logo">
            <HeartPulse size={27} />
          </div>

          <span className="section-label">
            ACCÈS SÉCURISÉ
          </span>

          <h2>Bienvenue</h2>

          <p className="login-subtitle">
            Connectez-vous à votre espace hospitalier.
          </p>

          {error && (
            <div className="login-error">
              {error}
            </div>
          )}

          <label>
            Identifiant

            <div className="input-wrapper">
              <UserRound size={18} />

              <input
                value={username}
                onChange={(event) =>
                  setUsername(event.target.value)
                }
                placeholder="Votre identifiant"
                autoComplete="username"
              />
            </div>
          </label>

          <label>
            Mot de passe

            <div className="input-wrapper">
              <LockKeyhole size={18} />

              <input
                type={
                  showPassword
                    ? "text"
                    : "password"
                }
                value={password}
                onChange={(event) =>
                  setPassword(event.target.value)
                }
                placeholder="Votre mot de passe"
                autoComplete="current-password"
              />

              <button
                type="button"
                className="password-toggle"
                onClick={() =>
                  setShowPassword(
                    (value) => !value
                  )
                }
                aria-label="Afficher ou masquer le mot de passe"
              >
                {showPassword ? (
                  <EyeOff size={18} />
                ) : (
                  <Eye size={18} />
                )}
              </button>
            </div>
          </label>

          <button
            className="login-submit"
            type="submit"
            disabled={loading}
          >
            {loading
              ? "Connexion..."
              : "Se connecter"}
          </button>

          <div className="demo-access">
            <strong>Accès de démonstration</strong>
            <span>Identifiant : admin</span>
            <span>Mot de passe : Demo123!</span>
          </div>
        </form>
      </section>
    </div>
  );
}
