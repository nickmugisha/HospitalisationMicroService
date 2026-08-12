import {
  Bell,
  CalendarDays,
  CreditCard,
  FileHeart,
  HeartPulse,
  LogOut,
  Pill,
  UserRound,
} from "lucide-react";

import {
  NavLink,
  Outlet,
  useNavigate,
} from "react-router-dom";

import {
  useAuth,
} from "../auth/AuthContext";

const patientMenu = [
  {
    label:
      "Mon espace",

    path:
      "/patient",

    icon:
      UserRound,

    end:
      true,
  },

  {
    label:
      "Mes rendez-vous",

    path:
      "/patient/rendez-vous",

    icon:
      CalendarDays,
  },

  {
    label:
      "Mes résultats",

    path:
      "/patient/resultats",

    icon:
      FileHeart,
  },

  {
    label:
      "Mes ordonnances",

    path:
      "/patient/ordonnances",

    icon:
      Pill,
  },

  {
    label:
      "Mes factures",

    path:
      "/patient/factures",

    icon:
      CreditCard,
  },

  {
    label:
      "Notifications",

    path:
      "/patient/notifications",

    icon:
      Bell,
  },
];

export default function PatientLayout() {
  const {
    user,
    logout,
  } =
    useAuth();

  const navigate =
    useNavigate();

  function handleLogout() {
    logout();

    navigate(
      "/login"
    );
  }

  return (
    <div className="patient-portal">
      <aside className="patient-sidebar">
        <div className="patient-brand">
          <div>
            <HeartPulse />
          </div>

          <span>
            <strong>
              HOSPITALIS
            </strong>

            <small>
              Espace Patient
            </small>
          </span>
        </div>

        <div className="patient-menu-label">
          MON ESPACE
        </div>

        <nav>
          {patientMenu.map(
            item => {
              const Icon =
                item.icon;

              return (
                <NavLink
                  key={
                    item.path
                  }
                  to={
                    item.path
                  }
                  end={
                    item.end
                  }
                  className={({
                    isActive,
                  }) =>
                    isActive
                      ? "patient-nav-link active"
                      : "patient-nav-link"
                  }
                >
                  <Icon
                    size={18}
                  />

                  {
                    item.label
                  }
                </NavLink>
              );
            }
          )}
        </nav>

        <div className="patient-sidebar-profile">
          <div className="patient-profile-avatar">
            {user?.fullName
              .charAt(0)
              .toUpperCase()}
          </div>

          <div>
            <strong>
              {
                user?.fullName
              }
            </strong>

            <span>
              {
                user?.patientNumber
              }
            </span>
          </div>
        </div>

        <button
          className="patient-logout"
          onClick={
            handleLogout
          }
        >
          <LogOut
            size={17}
          />

          Déconnexion
        </button>
      </aside>

      <main className="patient-main">
        <header className="patient-topbar">
          <div>
            <span>
              PORTAIL PATIENT
            </span>

            <strong>
              Votre santé,
              votre espace
            </strong>
          </div>

          <div className="patient-topbar-status">
            <span />

            Session sécurisée
          </div>
        </header>

        <div className="patient-content">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
