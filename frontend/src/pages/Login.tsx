import { useEffect, useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../lib/AuthContext";
import { AICFOAvatar, type AssistantExpression } from "../components/ai/AICFOAvatar";

type Phase = "idle" | "typing" | "submitting" | "success" | "error";

const BUBBLE: Record<Phase, string> = {
  idle: "Hi! I'm your AI CFO. Sign in and let's look at your numbers.",
  typing: "Nice. Take your time — I'm just watching the cursor.",
  submitting: "Checking your credentials…",
  success: "Welcome back! Loading your dashboard.",
  error: "Hmm, that didn't work. Check the details and try again.",
};

const EXPRESSION: Record<Phase, AssistantExpression> = {
  idle: "neutral",
  typing: "happy",
  submitting: "loading",
  success: "success",
  error: "error",
};

export function Login() {
  const { login, error, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const initialMode = params.get("mode") === "register" ? "register" : params.get("mode") === "forgot" ? "forgot" : "login";
  const [mode, setMode] = useState<"login" | "register" | "forgot">(initialMode);
  const [email, setEmail] = useState("owner@example.com");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [forgotSent, setForgotSent] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [phase, setPhase] = useState<Phase>("idle");
  const [shakeKey, setShakeKey] = useState(0);

  useEffect(() => {
    if (isAuthenticated) navigate("/dashboard", { replace: true });
  }, [isAuthenticated, navigate]);

  useEffect(() => {
    if (phase === "success" && mode !== "forgot") {
      const timer = window.setTimeout(() => navigate("/dashboard"), 700);
      return () => window.clearTimeout(timer);
    }
  }, [phase, navigate, mode]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (phase === "submitting" || phase === "success") return;
    if (mode === "forgot") {
      setForgotSent(true);
      setPhase("idle");
      return;
    }
    setPhase("submitting");
    try {
      await login(email, password);
      setPhase("success");
    } catch {
      // message is surfaced by the auth context
      setPhase("error");
      setShakeKey((k) => k + 1);
    }
  }

  const busy = phase === "submitting" || phase === "success";

  return (
    <div className="auth-shell">
      <section className="auth-hero" aria-label="FinSight AI introduction">
        <span className="auth-orb o1" aria-hidden="true" />
        <span className="auth-orb o2" aria-hidden="true" />
        <span className="auth-orb o3" aria-hidden="true" />
        <AICFOAvatar size={190} expression={EXPRESSION[phase]} label="FinSight AI robot" />
        <div className="auth-bubble" role="status" aria-live="polite">
          {BUBBLE[phase]}
        </div>
        <h2>Your Intelligent CFO</h2>
        <p>Analyze, predict, protect and optimize your business finances — with verified figures.</p>
        <div className="auth-chips" aria-hidden="true">
          <span>Forecasts</span>
          <span>Fraud checks</span>
          <span>What-if simulator</span>
          <span>Paper trading</span>
        </div>
      </section>

      <section className="auth-panel">
        <div className={`auth-card${shakeKey && phase === "error" ? " is-shaking" : ""}`} key={shakeKey}>
          <h1>FinSight AI</h1>
          <p className="page-lead">Executive Business Financial Intelligence</p>

          {mode !== "forgot" && (
            <div className="auth-tabs" role="tablist" aria-label="Authentication options">
              <button type="button" className={mode === "login" ? "active" : ""} onClick={() => { setMode("login"); setParams({ mode: "login" }); setPhase("idle"); }}>Login</button>
              <button type="button" className={mode === "register" ? "active" : ""} onClick={() => { setMode("register"); setParams({ mode: "register" }); setPhase("idle"); }}>Create Account</button>
            </div>
          )}

          <form className="auth-form" onSubmit={handleSubmit}>
            {mode === "register" && (
              <div className="field">
                <label htmlFor="fullName">Full Name</label>
                <input id="fullName" value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="Your name" autoComplete="name" required />
              </div>
            )}
            <div className="field">
              <label htmlFor="email">{mode === "forgot" ? "Account Email" : "Executive Email"}</label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value);
                  setPhase("typing");
                }}
                onFocus={() => phase === "idle" && setPhase("typing")}
                placeholder="name@company.com"
                autoComplete="email"
                required
              />
            </div>
            {mode !== "forgot" && <div className="field">
              <label htmlFor="password">Security Password</label>
              <input
                id="password"
                className="has-reveal"
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value);
                  setPhase("typing");
                }}
                placeholder="••••••••"
                autoComplete="current-password"
                required
              />
              <button
                type="button"
                className="reveal"
                onClick={() => setShowPassword((v) => !v)}
                aria-label={showPassword ? "Hide password" : "Show password"}
                aria-pressed={showPassword}
              >
                {showPassword ? "Hide" : "Show"}
              </button>
            </div>}

            {phase === "error" && error && (
              <p className="auth-error" role="alert">
                {error}
              </p>
            )}
            {phase === "success" && <p className="auth-success">Signed in successfully.</p>}
            {forgotSent && <p className="auth-success">If this demo account exists, password recovery instructions are ready for review.</p>}

            <button
              className={`btn btn-primary btn-lg${phase === "submitting" ? " is-loading" : ""}`}
              type="submit"
              disabled={busy}
              style={{ width: "100%" }}
            >
              {phase === "submitting"
                ? "Authenticating…"
                : mode === "register"
                  ? "Create Account"
                  : mode === "forgot"
                    ? "Request Recovery"
                    : phase === "success"
                      ? "Welcome!"
                      : "Sign In to Portal"}
            </button>
            {mode !== "forgot" ? (
              <button type="button" className="auth-link" onClick={() => { setMode("forgot"); setParams({ mode: "forgot" }); setForgotSent(false); }}>Forgot Password?</button>
            ) : (
              <button type="button" className="auth-link" onClick={() => { setMode("login"); setParams({ mode: "login" }); setForgotSent(false); }}>Back to Login</button>
            )}
          </form>

          <p className="auth-note">Demo Authentication Enabled · Any password accepted</p>
        </div>
      </section>
    </div>
  );
}
