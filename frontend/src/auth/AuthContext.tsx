import {
  createContext,
  useContext,
  useState,
  type ReactNode,
} from "react";

import type {
  AppRole,
} from "../config/modules";

export interface AuthUser {
  id: string;
  fullName: string;
  username: string;
  roles: AppRole[];

  patientNumber?: string;
}

interface AuthContextValue {
  user: AuthUser | null;

  isAuthenticated: boolean;

  login: (
    username: string,
    password: string
  ) => Promise<AuthUser | null>;

  logout: () => void;
}

const AuthContext =
  createContext<
    AuthContextValue | undefined
  >(undefined);

const DEMO_ADMIN:
  AuthUser = {
  id:
    "demo-admin",

  fullName:
    "Administrateur Hospitalis",

  username:
    "admin",

  roles:
    ["ADMIN"],
};

const DEMO_PATIENT:
  AuthUser = {
  id:
    "demo-patient",

  fullName:
    "kenny love",

  username:
    "patient",

  roles:
    ["PATIENT"],

  patientNumber:
    "PAT-2026-0003",
};

export function AuthProvider({
  children,
}: {
  children: ReactNode;
}) {
  const [
    user,
    setUser,
  ] =
    useState<AuthUser | null>(
      () => {
        const stored =
          localStorage.getItem(
            "hospitalis_user"
          );

        if (!stored) {
          return null;
        }

        try {
          return JSON.parse(
            stored
          ) as AuthUser;
        } catch {
          return null;
        }
      }
    );

  async function login(
    username: string,
    password: string
  ): Promise<AuthUser | null> {
    const normalizedUsername =
      username
        .trim()
        .toLowerCase();

    let authenticatedUser:
      AuthUser | null = null;

    if (
      normalizedUsername ===
        "admin" &&
      password ===
        "Demo123!"
    ) {
      authenticatedUser =
        DEMO_ADMIN;
    }

    if (
      normalizedUsername ===
        "patient" &&
      password ===
        "Patient123!"
    ) {
      authenticatedUser =
        DEMO_PATIENT;
    }

    if (!authenticatedUser) {
      return null;
    }

    localStorage.setItem(
      "hospitalis_user",
      JSON.stringify(
        authenticatedUser
      )
    );

    setUser(
      authenticatedUser
    );

    return authenticatedUser;
  }

  function logout() {
    localStorage.removeItem(
      "hospitalis_user"
    );

    setUser(null);
  }

  return (
    <AuthContext.Provider
      value={{
        user,

        isAuthenticated:
          Boolean(user),

        login,

        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context =
    useContext(
      AuthContext
    );

  if (!context) {
    throw new Error(
      "useAuth doit être utilisé à l'intérieur de AuthProvider"
    );
  }

  return context;
}
