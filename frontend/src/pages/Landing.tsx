import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../lib/AuthContext";
import { AICFOAvatar } from "../components/ai/AICFOAvatar";

const features = [
  ["01", "Financial Statement Analysis", "Turn financial statements into clear, decision-ready explanations."],
  ["02", "Budget & Variance", "Compare planned performance with actual results and identify meaningful gaps."],
  ["03", "Cash Flow Intelligence", "Understand liquidity, runway and the movements behind every cash decision."],
  ["04", "Capital Structure", "Review leverage, funding mix and financial stability from one perspective."],
  ["05", "Stock Market Intelligence", "Explore market signals and investment context with data-led analysis."],
  ["06", "Fraud Detection", "Surface unusual patterns and financial anomalies early."],
  ["07", "What-if Simulator", "Test assumptions and understand possible outcomes before acting."],
  ["08", "AI Financial Assistant", "Ask focused questions and receive clear, cited financial guidance."],
];

export function Landing() {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 16);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  function getStarted() {
    navigate(isAuthenticated ? "/dashboard" : "/login?mode=register");
  }

  function scrollToId(id: string) {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  return (
    <div className="landing">
      <header className={`landing-nav${scrolled ? " is-scrolled" : ""}`}>
        <button className="landing-brand" onClick={() => scrollToId("top")} aria-label="FinSight AI home">
          <span className="brand-mark">F</span>
          <span>FinSight <strong>AI</strong></span>
        </button>
        <nav aria-label="Primary navigation">
          <button onClick={() => scrollToId("platform")}>Platform</button>
          <button onClick={() => scrollToId("features")}>Features</button>
          <button onClick={() => scrollToId("how-it-works")}>How It Works</button>
          <button onClick={() => scrollToId("about")}>About</button>
        </nav>
        <div className="landing-nav-actions">
          <button className="landing-sign-in" onClick={() => navigate(isAuthenticated ? "/dashboard" : "/login?mode=login")}>
            Sign In
          </button>
          <button className="landing-primary landing-small" onClick={getStarted}>Get Started</button>
        </div>
      </header>

      <main>
        <section className="landing-hero" id="top">
          <div className="hero-copy">
            <span className="hero-badge"><i /> YOUR INTELLIGENT AI CFO</span>
            <h1>Your entire financial world,<br /><em>One intelligent AI CFO.</em></h1>
            <p>Understand your finances, predict future outcomes, detect financial risks and make smarter decisions with the power of AI — all in one intelligent platform.</p>
            <div className="hero-actions">
              <button className="landing-primary" onClick={getStarted}>Get Started <span aria-hidden="true">→</span></button>
              <button className="landing-secondary" onClick={() => scrollToId("platform")}>Explore Platform</button>
            </div>
            <div className="hero-services" aria-label="Platform capabilities">
              <span>Financial Analytics</span><i />
              <span>Cash Flow</span><i />
              <span>AI Assistant</span><i />
              <span>Fraud Detection</span><i />
              <span>Stock Intelligence</span>
            </div>
          </div>

          <div className="hero-visual" aria-label="FinSight AI dashboard preview">
            <div className="preview-shell">
              <div className="preview-topbar">
                <span className="preview-dot" />
                <span className="preview-dot" />
                <span className="preview-dot" />
                <span className="preview-title">Executive overview</span>
              </div>
              <div className="preview-body">
                <aside className="preview-sidebar">
                  <b>F</b><span /><span /><span /><span />
                </aside>
                <div className="preview-content">
                  <div className="preview-heading"><span>Financial Performance</span><small>Verified data</small></div>
                  <div className="preview-metrics">
                    <div><span>Profitability</span><strong>Analysis</strong></div>
                    <div><span>Cash Position</span><strong>Review</strong></div>
                    <div><span>Risk Status</span><strong>Monitor</strong></div>
                  </div>
                  <div className="preview-chart">
                    <div className="chart-bars" aria-hidden="true">
                      {[42, 58, 51, 72, 64, 82, 76, 88].map((height, index) => (
                        <span key={index} style={{ height: `${height}%` }} />
                      ))}
                    </div>
                    <div className="chart-line" aria-hidden="true" />
                  </div>
                </div>
              </div>
            </div>
            <div className="floating-insight"><span>AI CFO</span><strong>Insights ready</strong></div>
          </div>
        </section>

        <section className="landing-section what-section" id="platform">
          <div className="section-heading">
            <span>WHAT IS FINSIGHT AI?</span>
            <h2>A clearer view of every financial decision.</h2>
          </div>
          <div className="what-grid">
            <p>FinSight AI is an AI-powered financial management and intelligence platform that brings statements, budgets, cash flow, market context and risk monitoring into one practical workspace.</p>
            <p>Instead of leaving business owners to interpret scattered numbers alone, FinSight explains what matters, identifies patterns and helps evaluate the next decision.</p>
          </div>
        </section>

        <section className="landing-section" id="features">
          <div className="section-heading split-heading">
            <div><span>WHAT CAN IT DO?</span><h2>One platform.<br />Complete financial clarity.</h2></div>
            <p>Purpose-built intelligence for understanding performance, protecting the business and planning what comes next.</p>
          </div>
          <div className="feature-grid">
            {features.map(([number, title, description]) => (
              <article className="feature-card" key={title}>
                <span className="feature-number">{number}</span>
                <div className="feature-icon" aria-hidden="true">↗</div>
                <h3>{title}</h3>
                <p>{description}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="landing-section how-section" id="how-it-works">
          <div className="section-heading">
            <span>HOW IT WORKS</span>
            <h2>From financial information to confident action.</h2>
          </div>
          <div className="steps-grid">
            <article><b>01</b><h3>Connect or upload</h3><p>Add financial information and documents to your workspace.</p></article>
            <article><b>02</b><h3>Let AI analyze</h3><p>FinSight monitors, calculates and identifies meaningful patterns.</p></article>
            <article><b>03</b><h3>Act with clarity</h3><p>Understand insights and make more informed decisions.</p></article>
          </div>
        </section>

        <section className="landing-section companion-section" id="about">
          <div className="companion-copy">
            <span>MEET YOUR AI CFO</span>
            <h2>A financial companion that helps you think forward.</h2>
            <p>Ask questions in plain language and work through complex financial information with a friendly, always-ready AI assistant.</p>
            <button className="landing-secondary" onClick={() => navigate(isAuthenticated ? "/advisor" : "/login")}>Meet the AI Advisor</button>
          </div>
          <div className="companion-visual">
            <AICFOAvatar size={300} expression="happy" label="FinSight AI CFO companion" />
          </div>
        </section>

        <section className="landing-section dashboard-section">
          <div className="section-heading split-heading">
            <div><span>DASHBOARD PREVIEW</span><h2>Your financial picture, organized.</h2></div>
            <p>Explore a focused workspace for financial performance, risks, forecasts and reports.</p>
          </div>
          <div className="dashboard-preview">
            <div className="dashboard-preview-sidebar"><b>F</b><span>Overview</span><span>Analytics</span><span>Advisor</span><span>Reports</span></div>
            <div className="dashboard-preview-main">
              <div className="dashboard-preview-head"><strong>Executive overview</strong><span>Workspace</span></div>
              <div className="dashboard-preview-cards">
                <article><span>Performance</span><strong>Financial overview</strong></article>
                <article><span>Liquidity</span><strong>Cash analysis</strong></article>
                <article><span>Protection</span><strong>Risk monitoring</strong></article>
              </div>
              <div className="dashboard-preview-chart"><div className="preview-axis" /><div className="preview-bars"><i /><i /><i /><i /><i /><i /></div></div>
            </div>
          </div>
        </section>

        <section className="landing-section why-section">
          <div className="section-heading"><span>WHY FINSIGHT AI?</span><h2>Less complexity.<br />More visibility.</h2></div>
          <div className="why-grid">
            <article><strong>01</strong><h3>Better visibility</h3><p>See financial performance and priorities from one connected view.</p></article>
            <article><strong>02</strong><h3>Smarter decisions</h3><p>Use analysis and simulations to evaluate actions before committing.</p></article>
            <article><strong>03</strong><h3>Early risk identification</h3><p>Spot unusual patterns and potential issues earlier.</p></article>
            <article><strong>04</strong><h3>Simplified analysis</h3><p>Move from dense financial data to clear, understandable guidance.</p></article>
          </div>
        </section>

        <section className="landing-cta">
          <span>YOUR AI CFO IS READY</span>
          <h2>Make your next financial decision<br />with a clearer view.</h2>
          <button className="landing-primary" onClick={getStarted}>Get Started <span aria-hidden="true">→</span></button>
        </section>
      </main>

      <footer className="landing-footer">
        <button className="landing-brand" onClick={() => scrollToId("top")}><span className="brand-mark">F</span><span>FinSight <strong>AI</strong></span></button>
        <p>AI-powered business financial intelligence.</p>
        <button onClick={() => navigate("/login")}>Sign In</button>
      </footer>
    </div>
  );
}
