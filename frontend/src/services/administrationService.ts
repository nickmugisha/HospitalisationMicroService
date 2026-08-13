import type {
  HospitalUser,
  HospitalUserRole,
} from "../types/administration";

const STORAGE_KEY =
  "hospitalis_staff_users";

const now =
  new Date().toISOString();

const DEFAULT_USERS:
  HospitalUser[] = [
  {
    id:
      "staff-admin",

    fullName:
      "Administrateur Hospitalis",

    username:
      "admin",

    email:
      "admin@hospitalis.local",

    phone:
      "",

    role:
      "ADMIN",

    department:
      "Administration",

    active:
      true,

    createdAt:
      now,

    updatedAt:
      now,
  },

  {
    id:
      "doctor-jean",

    fullName:
      "Dr Jean Niyonzima",

    username:
      "j.niyonzima",

    email:
      "jean.niyonzima@hospitalis.local",

    phone:
      "",

    role:
      "DOCTOR",

    department:
      "Consultation",

    active:
      true,

    createdAt:
      now,

    updatedAt:
      now,
  },

  {
    id:
      "doctor-diane",

    fullName:
      "Dr Diane Ndayisenga",

    username:
      "d.ndayisenga",

    email:
      "diane.ndayisenga@hospitalis.local",

    phone:
      "",

    role:
      "DOCTOR",

    department:
      "Consultation",

    active:
      true,

    createdAt:
      now,

    updatedAt:
      now,
  },

  {
    id:
      "doctor-patrick",

    fullName:
      "Dr Patrick Nkurunziza",

    username:
      "p.nkurunziza",

    email:
      "patrick.nkurunziza@hospitalis.local",

    phone:
      "",

    role:
      "DOCTOR",

    department:
      "Hospitalisation",

    active:
      true,

    createdAt:
      now,

    updatedAt:
      now,
  },
];

function loadUsers():
  HospitalUser[] {
  const stored =
    localStorage.getItem(
      STORAGE_KEY
    );

  if (!stored) {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify(
        DEFAULT_USERS
      )
    );

    return DEFAULT_USERS;
  }

  try {
    return JSON.parse(
      stored
    ) as HospitalUser[];
  } catch {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify(
        DEFAULT_USERS
      )
    );

    return DEFAULT_USERS;
  }
}

function saveUsers(
  users: HospitalUser[]
) {
  localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify(
      users
    )
  );
}

export async function listHospitalUsers():
  Promise<HospitalUser[]> {
  return loadUsers()
    .sort(
      (a, b) =>
        a.fullName.localeCompare(
          b.fullName
        )
    );
}

export async function createHospitalUser(
  input: {
    fullName: string;
    username: string;
    email: string;
    phone: string;
    role: HospitalUserRole;
    department: string;
  }
): Promise<HospitalUser> {
  const users =
    loadUsers();

  if (
    !input.fullName.trim() ||
    !input.username.trim()
  ) {
    throw new Error(
      "Nom et identifiant obligatoires."
    );
  }

  const duplicate =
    users.some(
      user =>
        user.username
          .trim()
          .toLowerCase() ===
        input.username
          .trim()
          .toLowerCase()
    );

  if (duplicate) {
    throw new Error(
      "Cet identifiant est déjà utilisé."
    );
  }

  const timestamp =
    new Date().toISOString();

  const user:
    HospitalUser = {
    id:
      crypto.randomUUID(),

    fullName:
      input.fullName.trim(),

    username:
      input.username.trim(),

    email:
      input.email.trim(),

    phone:
      input.phone.trim(),

    role:
      input.role,

    department:
      input.department.trim(),

    active:
      true,

    createdAt:
      timestamp,

    updatedAt:
      timestamp,
  };

  users.push(
    user
  );

  saveUsers(
    users
  );

  return user;
}

export async function toggleHospitalUserStatus(
  userId: string
): Promise<HospitalUser> {
  const users =
    loadUsers();

  const index =
    users.findIndex(
      user =>
        user.id ===
        userId
    );

  if (index === -1) {
    throw new Error(
      "Utilisateur introuvable."
    );
  }

  users[index] = {
    ...users[index],

    active:
      !users[index].active,

    updatedAt:
      new Date().toISOString(),
  };

  saveUsers(
    users
  );

  return users[index];
}

export async function updateHospitalUserRole(
  userId: string,
  role: HospitalUserRole
): Promise<HospitalUser> {
  const users =
    loadUsers();

  const index =
    users.findIndex(
      user =>
        user.id ===
        userId
    );

  if (index === -1) {
    throw new Error(
      "Utilisateur introuvable."
    );
  }

  users[index] = {
    ...users[index],

    role,

    updatedAt:
      new Date().toISOString(),
  };

  saveUsers(
    users
  );

  return users[index];
}
