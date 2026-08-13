import {
  Navigate,
  Outlet,
  useLocation,
} from "react-router-dom";

import {
  useAuth,
} from "./AuthContext";

import {
  modules,
  type AppRole,
} from "../config/modules";

export default function ProtectedRoute() {
  const {
    isAuthenticated,
    user,
  } = useAuth();

  const location =
    useLocation();

  if (
    !isAuthenticated ||
    !user
  ) {
    return (
      <Navigate
        to="/login"
        replace
      />
    );
  }

  if (
    location.pathname === "/"
  ) {
    return <Outlet />;
  }

  const matchingModule =
    modules
      .filter(
        module =>
          module.path !== "/" &&
          (
            location.pathname ===
              module.path ||
            location.pathname.startsWith(
              `${module.path}/`
            )
          )
      )
      .sort(
        (a, b) =>
          b.path.length -
          a.path.length
      )[0];

  if (!matchingModule) {
    return <Outlet />;
  }

  if (
    matchingModule.roles.includes(
      "ALL"
    )
  ) {
    return <Outlet />;
  }

  const allowed =
    matchingModule.roles.some(
      role =>
        user.roles.includes(
          role as AppRole
        )
    );

  if (!allowed) {
    return (
      <Navigate
        to="/"
        replace
      />
    );
  }

  return <Outlet />;
}
