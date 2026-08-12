import {
  createContext,
  useContext,
  useState,
  type ReactNode,
} from "react";

import type { AppRole } from "../config/modules";

export interface AuthUser {
  id: string;
  fullName: string;
  username: string;
  roles: AppRole[];
}

interface AuthContextValue {
  user: AuthUser | null;
  isAuthenticated: boolean;
  login: (
    username: string,
    password: string
  ) => Promise<boolean>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(
  undefined
);

const DEMO_USER: AuthUser = {
  id: "demo-admin",
  fullName: "Administrateur Hospitalis",
  username: "admin",
  roles: ["ADMIN"],
};

export function AuthProvider({
  children,
}: {
  children: ReactNode;
}) {
  const [user, setUser] = useState<AuthUser | null>(() => {
    const stored = localStorage.getItem("hospitalis_user");

    if (!stored) return null;

    try {
      return JSON.parse(stored) as AuthUser;
    } catch {
      return null;
    }
  });

  async function login(
    username: string,
    password: string
  ): Promise<boolean> {
    // MODE DEMO TEMPORAIRE
    // Cette partie sera remplacée par le vrai AuthService gRPC.
    if (
      username.trim() === "admin" &&
      password === "Demo123!"
    ) {
      localStorage.setItem(
        "hospitalis_user",
        JSON.stringify(DEMO_USER)
      );

      setUser(DEMO_USER);

      return true;
    }

    return false;
  }

  function logout() {
    localStorage.removeItem("hospitalis_user");
    setUser(null);
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: Boolean(user),
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error(
      "useAuth doit être utilisé à l'intérieur de AuthProvider"
    );
  }

  return context;
}
