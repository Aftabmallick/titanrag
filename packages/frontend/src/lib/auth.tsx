"use client";

import React, { createContext, useContext, useEffect, useState, useCallback, ReactNode, useRef } from "react";
import { api, User, Workspace } from "./api";

interface AuthContextType {
  user: User | null;
  token: string | null;
  workspaces: Workspace[];
  activeWorkspace: Workspace | null;
  setActiveWorkspace: (ws: Workspace) => void;
  login: (email: string, pass: string) => Promise<void>;
  register: (data: { email: string; password: string; full_name: string; tenant_name?: string }) => Promise<void>;
  demoLogin: () => Promise<void>;
  logout: () => void;
  refreshWorkspaces: () => Promise<void>;
  refreshUser: () => Promise<void>;
  loading: boolean;
  error: string | null;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const DEMO_USER: User = {
  id: "ac885e2e-d938-428c-b1bf-43408554aca8",
  email: "admin@titanrag.io",
  full_name: "Titan Administrator",
  role: "OWNER",
  tenant_id: "4284c9db-eada-44ba-a415-0d71617fe4f1",
  onboarding_completed: true,
};

export const DEMO_WORKSPACE: Workspace = {
  id: "4a2f48a2-6615-4b05-ad60-6616cc11f01a",
  tenant_id: "4284c9db-eada-44ba-a415-0d71617fe4f1",
  name: "Default Workspace",
  description: "Enterprise Defense Knowledge Base",
  is_archived: false,
  created_at: new Date().toISOString(),
};

function setCookieToken(tokenValue: string | null) {
  if (typeof document === "undefined") return;
  if (tokenValue) {
    document.cookie = `titan_token=${encodeURIComponent(tokenValue)}; path=/; max-age=604800; SameSite=Lax`;
  } else {
    document.cookie = "titan_token=; path=/; max-age=0; SameSite=Lax";
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [activeWorkspace, setActiveWorkspace] = useState<Workspace | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const refreshTimerRef = useRef<NodeJS.Timeout | null>(null);

  const logout = useCallback(() => {
    if (refreshTimerRef.current) {
      clearInterval(refreshTimerRef.current);
      refreshTimerRef.current = null;
    }
    localStorage.removeItem("titan_token");
    setCookieToken(null);
    setToken(null);
    setUser(null);
    setWorkspaces([]);
    setActiveWorkspace(null);
  }, []);

  // Token auto-refresh cycle (runs every 8 minutes to guarantee 60s pre-expiration rotation for 10-15m JWTs)
  const scheduleTokenRefresh = useCallback(() => {
    if (refreshTimerRef.current) {
      clearInterval(refreshTimerRef.current);
    }
    refreshTimerRef.current = setInterval(async () => {
      const current = localStorage.getItem("titan_token");
      if (!current || current.startsWith("demo_")) return;

      try {
        const refreshed = await api.refreshToken();
        if (refreshed?.access_token) {
          localStorage.setItem("titan_token", refreshed.access_token);
          setCookieToken(refreshed.access_token);
          setToken(refreshed.access_token);
        }
      } catch (err: any) {
        console.warn("Silent token rotation failed, requiring re-auth:", err.message);
      }
    }, 8 * 60 * 1000); // 8 minutes
  }, []);

  const initAuth = useCallback(async (currentToken: string) => {
    try {
      setLoading(true);
      setCookieToken(currentToken);
      if (currentToken === "demo_token_admin" || currentToken.startsWith("demo_")) {
        setUser(DEMO_USER);
        setWorkspaces([DEMO_WORKSPACE]);
        setActiveWorkspace(DEMO_WORKSPACE);
        setError(null);
        return;
      }

      try {
        const me = await api.getMe();
        setUser(me);

        const wsList = await api.listWorkspaces();
        setWorkspaces(wsList);
        if (wsList.length > 0) {
          setActiveWorkspace((prev) => {
            if (prev && wsList.some((w) => w.id === prev.id)) return prev;
            return wsList[0];
          });
        }
        setError(null);
        scheduleTokenRefresh();
      } catch (backendErr: any) {
        console.warn("Backend offline during initAuth, activating demo sandbox:", backendErr.message);
        setUser(DEMO_USER);
        setWorkspaces([DEMO_WORKSPACE]);
        setActiveWorkspace(DEMO_WORKSPACE);
        setError(null);
      }
    } catch (err: any) {
      console.warn("Auth initialization failed:", err.message);
      logout();
    } finally {
      setLoading(false);
    }
  }, [logout, scheduleTokenRefresh]);

  useEffect(() => {
    const savedToken = localStorage.getItem("titan_token");
    if (savedToken) {
      setToken(savedToken);
      initAuth(savedToken);
    } else {
      setLoading(false);
    }

    const handleUnauthorized = () => {
      logout();
    };

    window.addEventListener("titan:unauthorized", handleUnauthorized);
    return () => {
      window.removeEventListener("titan:unauthorized", handleUnauthorized);
      if (refreshTimerRef.current) clearInterval(refreshTimerRef.current);
    };
  }, [initAuth, logout]);

  const login = async (email: string, pass: string) => {
    setError(null);
    try {
      const res = await api.login(email, pass);
      localStorage.setItem("titan_token", res.access_token);
      setCookieToken(res.access_token);
      setToken(res.access_token);
      await initAuth(res.access_token);
    } catch (err: any) {
      setError(err.message || "Login failed");
      throw err;
    }
  };

  const register = async (data: { email: string; password: string; full_name: string; tenant_name?: string }) => {
    setError(null);
    try {
      const res = await api.register(data);
      localStorage.setItem("titan_token", res.access_token);
      setCookieToken(res.access_token);
      setToken(res.access_token);
      await initAuth(res.access_token);
    } catch (err: any) {
      setError(err.message || "Registration failed");
      throw err;
    }
  };

  const demoLogin = async () => {
    setError(null);
    setLoading(true);
    try {
      // First try live backend login
      try {
        const res = await api.login("admin@titanrag.io", "TitanAdmin123!");
        localStorage.setItem("titan_token", res.access_token);
        setCookieToken(res.access_token);
        setToken(res.access_token);
        await initAuth(res.access_token);
        return;
      } catch {
        // Try live register
        try {
          const regRes = await api.register({
            email: "admin@titanrag.io",
            password: "TitanAdmin123!",
            full_name: "Titan Administrator",
            tenant_name: "Enterprise Default",
          });
          localStorage.setItem("titan_token", regRes.access_token);
          setCookieToken(regRes.access_token);
          setToken(regRes.access_token);
          await initAuth(regRes.access_token);
          return;
        } catch {
          // Backend offline -> engage instant demo sandbox
          console.info("Backend core unreachable. Engaging instant in-browser admin sandbox.");
        }
      }

      // Launch Instant Demo Sandbox
      const demoToken = "demo_token_admin";
      localStorage.setItem("titan_token", demoToken);
      setCookieToken(demoToken);
      setToken(demoToken);
      setUser(DEMO_USER);
      setWorkspaces([DEMO_WORKSPACE]);
      setActiveWorkspace(DEMO_WORKSPACE);
    } catch (err: any) {
      setError(err.message || "Demo login failed");
    } finally {
      setLoading(false);
    }
  };

  const refreshWorkspaces = async () => {
    if (!token) return;
    try {
      const wsList = await api.listWorkspaces();
      setWorkspaces(wsList);
      if (wsList.length > 0 && (!activeWorkspace || !wsList.some((w) => w.id === activeWorkspace.id))) {
        setActiveWorkspace(wsList[0]);
      }
    } catch (err: any) {
      console.error("Failed to refresh workspaces:", err.message);
    }
  };

  const refreshUser = async () => {
    if (!token) return;
    try {
      const me = await api.getMe();
      setUser(me);
    } catch (err: any) {
      console.error("Failed to refresh user:", err.message);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        workspaces,
        activeWorkspace,
        setActiveWorkspace,
        login,
        register,
        demoLogin,
        logout,
        refreshWorkspaces,
        refreshUser,
        loading,
        error,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
