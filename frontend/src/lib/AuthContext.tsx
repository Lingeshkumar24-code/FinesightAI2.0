import { createContext, useContext, useState, useCallback, type ReactNode } from "react";
import { api, setAuthToken, loadStoredToken, ApiError } from "./api";

interface AuthState {
  isAuthenticated: boolean;
  businessId: string | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  error: string | null;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const existingToken = loadStoredToken();
  const [isAuthenticated, setIsAuthenticated] = useState(Boolean(existingToken));
  const [businessId, setBusinessId] = useState<string | null>(
    existingToken ? localStorage.getItem("finsight_business_id") : null
  );
  const [error, setError] = useState<string | null>(null);

  const login = useCallback(async (email: string, password: string) => {
    setError(null);
    try {
      const resp = await api.login(email, password);
      setAuthToken(resp.access_token);
      localStorage.setItem("finsight_business_id", resp.business_id);
      setBusinessId(resp.business_id);
      setIsAuthenticated(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Login failed");
      throw err;
    }
  }, []);

  const logout = useCallback(() => {
    setAuthToken(null);
    localStorage.removeItem("finsight_business_id");
    setIsAuthenticated(false);
    setBusinessId(null);
  }, []);

  return (
    <AuthContext.Provider value={{ isAuthenticated, businessId, login, logout, error }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
