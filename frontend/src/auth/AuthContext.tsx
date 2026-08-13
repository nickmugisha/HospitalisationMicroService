import {
  createContext,
  useContext,
  useState,
  type ReactNode,
} from "react";

import {
  listHospitalUsers,
} from "../services/administrationService";

import type {
  HospitalUser,
  HospitalUserRole,
} from "../types/administration";

import type {
  AppRole,
} from "../config/modules";

export interface AuthUser {
  id: string;
  fullName: string;
  username: string;

  roles: AppRole[];

  department?: string;
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

  department:
    "Administration",
};

function hospitalRoleToAppRoles(
  staff: HospitalUser
): AppRole[] {
  const role:
    HospitalUserRole =
    staff.role;

  switch (role) {
    case "ADMIN":
      return ["ADMIN"];

    case "RECEPTION":
      return [
        "ACCUEIL",
        "RENDEZ_VOUS",
      ];

    case "DOCTOR":
      return [
        "MEDECIN",
      ];

    case "NURSE":
      return [
        "HOSPITALISATION",
      ];

    case "LAB_TECH":
      return [
        "LABORATOIRE",
      ];

    case "PHARMACIST":
      return [
        "PHARMACIEN",
      ];

    case "BILLING":
      return [
        "CAISSIER",
      ];

    case "MATERNITY":
      return [
        "MATERNITE",
      ];

    case "MANAGER":
      return [
        "DIRECTION",
      ];
  }
}

function buildStaffAuthUser(
  staff: HospitalUser
): AuthUser {
  return {
    id:
      staff.id,

    fullName:
      staff.fullName,

    username:
      staff.username,

    roles:
      hospitalRoleToAppRoles(
        staff
      ),

    department:
      staff.department,
  };
}

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
          const parsed =
            JSON.parse(
              stored
            ) as AuthUser;

          return parsed;
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
      !authenticatedUser &&
      password ===
        "Hospital123!"
    ) {
      const staffUsers =
        await listHospitalUsers();

      const staff =
        staffUsers.find(
          current =>
            current.username
              .trim()
              .toLowerCase() ===
            normalizedUsername
        );

      if (
        staff &&
        staff.active
      ) {
        authenticatedUser =
          buildStaffAuthUser(
            staff
          );
      }
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
