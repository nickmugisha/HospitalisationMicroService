import {
  Bell,
  CheckCircle2,
  Plus,
  Search,
  ShieldCheck,
  UserCheck,
  Users,
  UserX,
  X,
} from "lucide-react";

import {
  useEffect,
  useMemo,
  useState,
  type FormEvent,
} from "react";

import {
  createHospitalUser,
  listHospitalUsers,
  toggleHospitalUserStatus,
  updateHospitalUserRole,
} from "../services/administrationService";

import {
  listNotifications,
  markNotificationRead,
} from "../services/notificationService";

import type {
  HospitalNotification,
  HospitalUser,
  HospitalUserRole,
} from "../types/administration";

const roles:
  HospitalUserRole[] = [
  "ADMIN",
  "RECEPTION",
  "DOCTOR",
  "NURSE",
  "LAB_TECH",
  "PHARMACIST",
  "BILLING",
  "MATERNITY",
  "MANAGER",
];

function roleLabel(
  role:
    HospitalUserRole
) {
  switch (role) {
    case "ADMIN":
      return "Administrateur";

    case "RECEPTION":
      return "Accueil";

    case "DOCTOR":
      return "Médecin";

    case "NURSE":
      return "Infirmier";

    case "LAB_TECH":
      return "Laboratoire";

    case "PHARMACIST":
      return "Pharmacien";

    case "BILLING":
      return "Facturation";

    case "MATERNITY":
      return "Maternité";

    case "MANAGER":
      return "Direction";
  }
}

export default function AdministrationPage() {
  const [
    users,
    setUsers,
  ] =
    useState<
      HospitalUser[]
    >([]);

  const [
    notifications,
    setNotifications,
  ] =
    useState<
      HospitalNotification[]
    >([]);

  const [
    tab,
    setTab,
  ] =
    useState<
      "USERS" |
      "NOTIFICATIONS"
    >("USERS");

  const [
    search,
    setSearch,
  ] =
    useState("");

  const [
    showCreate,
    setShowCreate,
  ] =
    useState(false);

  const [
    error,
    setError,
  ] =
    useState("");

  const [
    fullName,
    setFullName,
  ] =
    useState("");

  const [
    username,
    setUsername,
  ] =
    useState("");

  const [
    email,
    setEmail,
  ] =
    useState("");

  const [
    phone,
    setPhone,
  ] =
    useState("");

  const [
    role,
    setRole,
  ] =
    useState<
      HospitalUserRole
    >("DOCTOR");

  const [
    department,
    setDepartment,
  ] =
    useState("");

  async function refresh() {
    const [
      staff,
      adminNotifications,
    ] =
      await Promise.all([
        listHospitalUsers(),

        listNotifications(
          "STAFF",
          "ADMIN"
        ),
      ]);

    setUsers(staff);

    setNotifications(
      adminNotifications
    );
  }

  useEffect(() => {
    refresh();
  }, []);

  const filteredUsers =
    useMemo(() => {
      const value =
        search
          .trim()
          .toLowerCase();

      if (!value) {
        return users;
      }

      return users.filter(
        user =>
          [
            user.fullName,
            user.username,
            user.email,
            user.department,
            roleLabel(
              user.role
            ),
          ]
            .join(" ")
            .toLowerCase()
            .includes(value)
      );
    }, [
      users,
      search,
    ]);

  const active =
    users.filter(
      user =>
        user.active
    ).length;

  const doctors =
    users.filter(
      user =>
        user.role ===
        "DOCTOR"
    ).length;

  const unread =
    notifications.filter(
      notification =>
        !notification.read
    ).length;

  async function handleCreate(
    event:
      FormEvent<HTMLFormElement>
  ) {
    event.preventDefault();

    setError("");

    try {
      await createHospitalUser({
        fullName,
        username,
        email,
        phone,
        role,
        department,
      });

      setShowCreate(false);

      setFullName("");
      setUsername("");
      setEmail("");
      setPhone("");
      setDepartment("");

      await refresh();
    } catch (exception) {
      setError(
        exception instanceof Error
          ? exception.message
          : "Création impossible."
      );
    }
  }

  async function handleStatus(
    userId: string
  ) {
    await toggleHospitalUserStatus(
      userId
    );

    await refresh();
  }

  async function handleRole(
    userId: string,
    nextRole:
      HospitalUserRole
  ) {
    await updateHospitalUserRole(
      userId,
      nextRole
    );

    await refresh();
  }

  async function readNotification(
    notificationId:
      string
  ) {
    await markNotificationRead(
      notificationId
    );

    await refresh();
  }

  return (
    <div className="administration-page">
      <header className="topbar">
        <div>
          <p className="eyebrow">
            SERVICE 09 •
            AUTHENTIFICATION &
            NOTIFICATIONS
          </p>

          <h1>
            Utilisateurs &
            notifications
          </h1>

          <p className="subtitle">
            Personnel hospitalier,
            rôles, accès et centre
            de notifications.
          </p>
        </div>

        <button
          className="primary-action"
          onClick={() =>
            setShowCreate(true)
          }
        >
          <Plus size={18} />
          Nouvel utilisateur
        </button>
      </header>

      <section className="dashboard-stats">
        <article>
          <div className="stat-icon">
            <Users />
          </div>

          <div>
            <span>
              Utilisateurs
            </span>

            <strong>
              {users.length}
            </strong>
          </div>
        </article>

        <article>
          <div className="stat-icon">
            <UserCheck />
          </div>

          <div>
            <span>
              Comptes actifs
            </span>

            <strong>
              {active}
            </strong>
          </div>
        </article>

        <article>
          <div className="stat-icon">
            <ShieldCheck />
          </div>

          <div>
            <span>
              Médecins
            </span>

            <strong>
              {doctors}
            </strong>
          </div>
        </article>

        <article>
          <div className="stat-icon">
            <Bell />
          </div>

          <div>
            <span>
              Notifications non lues
            </span>

            <strong>
              {unread}
            </strong>
          </div>
        </article>
      </section>

      <section className="admin-tabs">
        <button
          className={
            tab === "USERS"
              ? "active"
              : ""
          }
          onClick={() =>
            setTab("USERS")
          }
        >
          <Users size={17} />
          Personnel
        </button>

        <button
          className={
            tab ===
            "NOTIFICATIONS"
              ? "active"
              : ""
          }
          onClick={() =>
            setTab(
              "NOTIFICATIONS"
            )
          }
        >
          <Bell size={17} />
          Notifications

          {unread > 0 && (
            <span>
              {unread}
            </span>
          )}
        </button>
      </section>

      {tab === "USERS" && (
        <section className="admin-users-card">
          <div className="panel-heading">
            <div>
              <span className="section-label">
                PERSONNEL
              </span>

              <h2>
                Utilisateurs hospitaliers
              </h2>
            </div>

            <div className="patient-search">
              <Search size={17} />

              <input
                value={search}
                onChange={event =>
                  setSearch(
                    event.target.value
                  )
                }
                placeholder="Nom, rôle, service..."
              />
            </div>
          </div>

          <div className="patient-table-wrapper">
            <table className="patient-table">
              <thead>
                <tr>
                  <th>Utilisateur</th>
                  <th>Identifiant</th>
                  <th>Service</th>
                  <th>Rôle</th>
                  <th>Statut</th>
                  <th>Action</th>
                </tr>
              </thead>

              <tbody>
                {filteredUsers.map(
                  user => (
                    <tr
                      key={
                        user.id
                      }
                    >
                      <td>
                        <div className="patient-name">
                          <div className="patient-avatar">
                            {user.fullName
                              .charAt(0)
                              .toUpperCase()}
                          </div>

                          <div>
                            <strong>
                              {
                                user.fullName
                              }
                            </strong>

                            <span>
                              {
                                user.email ||
                                "Aucun email"
                              }
                            </span>
                          </div>
                        </div>
                      </td>

                      <td>
                        <code>
                          {
                            user.username
                          }
                        </code>
                      </td>

                      <td>
                        {
                          user.department ||
                          "—"
                        }
                      </td>

                      <td>
                        <select
                          className="admin-role-select"
                          value={
                            user.role
                          }
                          onChange={event =>
                            handleRole(
                              user.id,
                              event.target
                                .value as HospitalUserRole
                            )
                          }
                        >
                          {roles.map(
                            current => (
                              <option
                                key={
                                  current
                                }
                                value={
                                  current
                                }
                              >
                                {
                                  roleLabel(
                                    current
                                  )
                                }
                              </option>
                            )
                          )}
                        </select>
                      </td>

                      <td>
                        <span
                          className={
                            user.active
                              ? "admin-user-status active"
                              : "admin-user-status inactive"
                          }
                        >
                          {user.active
                            ? "Actif"
                            : "Désactivé"}
                        </span>
                      </td>

                      <td>
                        <button
                          className={
                            user.active
                              ? "admin-disable-button"
                              : "admin-enable-button"
                          }
                          onClick={() =>
                            handleStatus(
                              user.id
                            )
                          }
                        >
                          {user.active ? (
                            <>
                              <UserX
                                size={15}
                              />
                              Désactiver
                            </>
                          ) : (
                            <>
                              <UserCheck
                                size={15}
                              />
                              Activer
                            </>
                          )}
                        </button>
                      </td>
                    </tr>
                  )
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {tab ===
        "NOTIFICATIONS" && (
        <section className="admin-notification-list">
          {notifications.map(
            notification => (
              <button
                key={
                  notification.id
                }
                className={
                  notification.read
                    ? "admin-notification-card"
                    : "admin-notification-card unread"
                }
                onClick={() =>
                  readNotification(
                    notification.id
                  )
                }
              >
                <div>
                  <Bell />
                </div>

                <section>
                  <strong>
                    {
                      notification.title
                    }
                  </strong>

                  <p>
                    {
                      notification.message
                    }
                  </p>

                  <small>
                    {new Intl.DateTimeFormat(
                      "fr-FR",
                      {
                        dateStyle:
                          "medium",

                        timeStyle:
                          "short",
                      }
                    ).format(
                      new Date(
                        notification.createdAt
                      )
                    )}
                  </small>
                </section>

                {!notification.read && (
                  <span className="notification-unread-dot" />
                )}
              </button>
            )
          )}

          {notifications.length ===
            0 && (
            <div className="patient-empty-state">
              <CheckCircle2 />

              <h2>
                Aucune notification
              </h2>

              <p>
                Les nouvelles demandes
                patients apparaîtront ici.
              </p>
            </div>
          )}
        </section>
      )}

      {showCreate && (
        <div className="modal-backdrop">
          <form
            className="patient-modal"
            onSubmit={
              handleCreate
            }
          >
            <div className="modal-header">
              <div>
                <span className="section-label">
                  PERSONNEL
                </span>

                <h2>
                  Nouvel utilisateur
                </h2>
              </div>

              <button
                type="button"
                className="modal-close"
                onClick={() =>
                  setShowCreate(false)
                }
              >
                <X size={20} />
              </button>
            </div>

            {error && (
              <div className="login-error">
                {error}
              </div>
            )}

            <div className="form-grid">
              <label>
                Nom complet *

                <input
                  value={
                    fullName
                  }
                  onChange={event =>
                    setFullName(
                      event.target.value
                    )
                  }
                  required
                />
              </label>

              <label>
                Identifiant *

                <input
                  value={
                    username
                  }
                  onChange={event =>
                    setUsername(
                      event.target.value
                    )
                  }
                  required
                />
              </label>

              <label>
                Email

                <input
                  type="email"
                  value={
                    email
                  }
                  onChange={event =>
                    setEmail(
                      event.target.value
                    )
                  }
                />
              </label>

              <label>
                Téléphone

                <input
                  value={
                    phone
                  }
                  onChange={event =>
                    setPhone(
                      event.target.value
                    )
                  }
                />
              </label>

              <label>
                Rôle *

                <select
                  value={
                    role
                  }
                  onChange={event =>
                    setRole(
                      event.target
                        .value as HospitalUserRole
                    )
                  }
                >
                  {roles.map(
                    current => (
                      <option
                        key={
                          current
                        }
                        value={
                          current
                        }
                      >
                        {
                          roleLabel(
                            current
                          )
                        }
                      </option>
                    )
                  )}
                </select>
              </label>

              <label>
                Service

                <input
                  value={
                    department
                  }
                  onChange={event =>
                    setDepartment(
                      event.target.value
                    )
                  }
                  placeholder="Consultation, laboratoire..."
                />
              </label>
            </div>

            <div className="modal-actions">
              <button
                type="button"
                className="secondary-action"
                onClick={() =>
                  setShowCreate(false)
                }
              >
                Annuler
              </button>

              <button
                type="submit"
                className="primary-action"
              >
                <Plus size={17} />
                Créer utilisateur
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
