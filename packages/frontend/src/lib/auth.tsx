"use client";

import React, { createContext, useContext, useEffect, useState, useCallback, ReactNode } from "react";
import { api, User, Workspace } from "./api";

interface AuthContextType {
  user: User | null;
  token: string | null;
  workspaces: Workspace[];
  activeWorkspace: Workspace | null;
  setActiveWorkspace: (ws: Workspace) => void;
  login: (email: string, pass: string) => Promise<void>;
  demoLogin: () => Promise<void>;
  logout: () => void;
  refreshWorkspaces: () => Promise<void>;
  refreshUser: () => Promise<void>;
  loading: boolean;
  error: string | null;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [activeWorkspace, setActiveWorkspace] = useState<Workspace | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const logout = useCallback(() => {
    localStorage.removeItem("titan_token");
    setToken(null);
    setUser(null);
    setWorkspaces([]);
    setActiveWorkspace(null);
  }, []);

  const initAuth = useCallback(async (currentToken: string) => {
    try {
      setLoading(true);
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
    } catch (err: any) {
      console.warn("Auth initialization failed:", err.message);
      logout();
    } finally {
      setLoading(false);
    }
  }, [logout]);

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
    return () => window.removeEventListener("titan:unauthorized", handleUnauthorized);
  }, [initAuth, logout]);

  const login = async (email: string, pass: string) => {
    setError(null);
    try {
      const res = await api.login(email, pass);
      localStorage.setItem("titan_token", res.access_token);
      setToken(res.access_token);
      await initAuth(res.access_token);
    } catch (err: any) {
      setError(err.message || "Login failed");
      throw err;
    }
  };

  const demoLogin = async () => {
    setError(null);
    try {
      // First try login with default admin credentials
      try {
        await login("admin@titanrag.io", "TitanAdmin123!");
      } catch {
        // If user doesn't exist yet, register them
        const regRes = await api.register({
          email: "admin@titanrag.io",
          password: "TitanAdmin123!",
          full_name: "Titan Administrator",
          tenant_name: "Enterprise Default",
        });
        localStorage.setItem("titan_token", regRes.access_token);
        setToken(regRes.access_token);
        await initAuth(regRes.access_token);
      }
    } catch (err: any) {
      setError(err.message || "Demo login failed");
      throw err;
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
