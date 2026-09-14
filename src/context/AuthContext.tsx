/**
 * ContractIQ — Authentication Context & Provider
 */

import React, { createContext, useContext, useEffect, useState } from "react";
import { authApi } from "../api/services";
import { tokenStorage } from "../api/client";
import type { UserResponse } from "../api/types";

interface AuthContextType {
  user: UserResponse | null;
  token: string | null;
  isLoading: boolean;
  login: (token: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(tokenStorage.get());
  const [user, setUser] = useState<UserResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  async function loadUser(authToken: string) {
    try {
      const userData = await authApi.getMe();
      setUser(userData);
    } catch {
      // Invalid/expired token
      tokenStorage.clear();
      setToken(null);
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    const savedToken = tokenStorage.get();
    if (savedToken) {
      loadUser(savedToken);
    } else {
      setIsLoading(false);
    }

    const handleUnauthorized = () => {
      logout();
    };

    window.addEventListener("contractiq:unauthorized", handleUnauthorized);
    return () => {
      window.removeEventListener("contractiq:unauthorized", handleUnauthorized);
    };
  }, []);

  const login = async (newToken: string) => {
    tokenStorage.set(newToken);
    setToken(newToken);
    setIsLoading(true);
    await loadUser(newToken);
  };

  const logout = () => {
    tokenStorage.clear();
    setToken(null);
    setUser(null);
  };

  const refreshUser = async () => {
    if (token) {
      await loadUser(token);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isLoading,
        login,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
