import React, { createContext, useState, useEffect, useCallback } from "react";

import * as authService from "../services/auth";

export const AuthContext = createContext({
  user: null,
  loading: true,
  login: async () => {},
  signup: async () => {},
  logout: () => {},
});

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const setSession = useCallback((token) => {
    authService.setAuthToken(token ?? null);
  }, []);

  useEffect(() => {
    let active = true;

    const init = async () => {
      setLoading(true);
      try {
        const token = authService.readStoredToken();
        if (token) {
          const me = await authService.getCurrentUser();
          if (active) {
            setUser(me);
          }
        } else {
          if (active) {
            setUser(null);
          }
        }
      } catch (err) {
        console.error("Auth init error:", err);
        if (active) {
          setUser(null);
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };

    init();
    return () => {
      active = false;
    };
  }, []);

  const login = async (creds) => {
    setLoading(true);
    try {
      const res = await authService.login(creds);
      const token = res?.access_token ?? null;
      if (!token) throw new Error("No token returned from login");
      setSession(token);
      setUser(res?.user ?? (await authService.getCurrentUser()));
      return res;
    } finally {
      setLoading(false);
    }
  };

  const signup = async (payload) => {
    setLoading(true);
    try {
      const res = await authService.signup(payload);
      const token = res?.access_token ?? null;
      if (token) {
        setSession(token);
        setUser(res?.user ?? (await authService.getCurrentUser()));
      }
      return res;
    } finally {
      setLoading(false);
    }
  };

  const logout = () => {
    setSession(null);
    setUser(null);
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    authService.logout().catch(() => {});
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export default { AuthContext };
