import {
  Navigate,
  Outlet,
  useLocation,
} from "react-router-dom";

import {
  useAuth,
} from "./AuthContext";

export default function ProtectedRoute() {
  const {
    isAuthenticated,
    user,
  } =
    useAuth();

  const location =
    useLocation();

  if (!isAuthenticated) {
    return (
      <Navigate
        to="/login"
        replace
      />
    );
  }

  const isPatient =
    user?.roles.includes(
      "PATIENT"
    ) ?? false;

  const isPatientArea =
    location.pathname ===
      "/patient" ||
    location.pathname.startsWith(
      "/patient/"
    );

  /*
   * Patient essayant d'entrer
   * dans l'espace personnel/admin.
   */
  if (
    isPatient &&
    !isPatientArea
  ) {
    return (
      <Navigate
        to="/patient"
        replace
      />
    );
  }

  /*
   * Personnel essayant d'entrer
   * dans un espace patient.
   */
  if (
    !isPatient &&
    isPatientArea
  ) {
    return (
      <Navigate
        to="/"
        replace
      />
    );
  }

  return <Outlet />;
}
