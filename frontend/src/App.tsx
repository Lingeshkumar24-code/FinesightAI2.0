import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./lib/AuthContext";
import { Layout } from "./components/layout/Layout";
import { Login } from "./pages/Login";
import { Dashboard } from "./pages/Dashboard";
import { Upload } from "./pages/Upload";
import { AIAdvisor } from "./pages/AIAdvisor";
import { Simulator } from "./pages/Simulator";
import { Reports } from "./pages/Reports";
import { Alerts } from "./pages/Alerts";
import { MarketIntelligence } from "./pages/MarketIntelligence";
import { PaperTrading } from "./pages/PaperTrading";
import { MoneyManagement } from "./pages/MoneyManagement";
import { FraudDetection } from "./pages/FraudDetection";
import { DocumentVerification } from "./pages/DocumentVerification";
import { Automation } from "./pages/Automation";
import { Landing } from "./pages/Landing";

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/upload" element={<Upload />} />
        <Route path="/advisor" element={<AIAdvisor />} />
        <Route path="/simulator" element={<Simulator />} />
        <Route path="/market" element={<MarketIntelligence />} />
        <Route path="/trading" element={<PaperTrading />} />
        <Route path="/money" element={<MoneyManagement />} />
        <Route path="/fraud" element={<FraudDetection />} />
        <Route path="/verification" element={<DocumentVerification />} />
        <Route path="/automation" element={<Automation />} />
        <Route path="/reports" element={<Reports />} />
        <Route path="/alerts" element={<Alerts />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  );
}
