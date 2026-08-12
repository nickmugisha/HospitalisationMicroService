import {
  Bell,
  ChevronDown,
  HeartPulse,
  LogOut,
} from "lucide-react";
import {
  NavLink,
  Outlet,
} from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { modules } from "../config/modules";

export default function AppLayout() {
  const {
    user,
    logout,
  } = useAuth();

  const visibleModules =
    modules.filter((module) => {
      if (
        module.roles.includes("ALL")
      ) {
        return true;
      }

      return module.roles.some((role) =>
        user?.roles.includes(role as never)
      );
    });

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-logo">
            <HeartPulse size={27} />
          </div>

          <div>
            <strong>HOSPITALIS</strong>
            <span>MicroServices</span>
          </div>
        </div>

        <div className="menu-title">
          NAVIGATION
        </div>

        <nav className="navigation">
          {visibleModules.map(
            ({ id, label, path, icon: Icon }) => (
              <NavLink
                key={id}
                to={path}
                end={path === "/"}
                className={({ isActive }) =>
                  `nav-item ${
                    isActive ? "active" : ""
                  }`
                }
              >
                <Icon size={19} />
                <span>{label}</span>
              </NavLink>
            )
          )}
        </nav>

        <div className="sidebar-footer">
          <span className="client-dot" />
          Client Linux
        </div>
      </aside>

      <main className="main-content">
        <div className="global-header">
          <div className="connection-chip">
            <span className="client-dot" />
            Session active
          </div>

          <div className="header-actions">
            <button
              className="icon-button"
              aria-label="Notifications"
            >
              <Bell size={19} />
            </button>

            <div className="user-box">
              <div className="user-avatar">
                {user?.fullName
                  .charAt(0)
                  .toUpperCase()}
              </div>

              <div>
                <strong>
                  {user?.fullName}
                </strong>

                <span>
                  {user?.roles.join(", ")}
                </span>
              </div>

              <ChevronDown size={16} />
            </div>

            <button
              className="logout-button"
              onClick={logout}
            >
              <LogOut size={17} />
              Déconnexion
            </button>
          </div>
        </div>

        <Outlet />
      </main>
    </div>
  );
}
