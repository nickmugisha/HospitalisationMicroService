import {
  Activity,
  Baby,
  BarChart3,
  CalendarDays,
  CreditCard,
  FlaskConical,
  Hospital,
  MessageCircleMore,
  Pill,
  ShieldCheck,
  Stethoscope,
  UserRoundPlus,
} from "lucide-react";

export type AppRole =
  | "PATIENT"
  | "ADMIN"
  | "ACCUEIL"
  | "MEDECIN"
  | "LABORATOIRE"
  | "PHARMACIEN"
  | "HOSPITALISATION"
  | "CAISSIER"
  | "MATERNITE"
  | "RENDEZ_VOUS"
  | "DIRECTION";

export const modules = [
  {
    id: "dashboard",
    label: "Tableau de bord",
    path: "/",
    icon: Activity,
    roles: ["ALL"],
  },
  {
    id: "accueil",
    label: "Accueil",
    path: "/accueil",
    icon: UserRoundPlus,
    roles: ["ADMIN", "ACCUEIL"],
  },
  {
    id: "hospitalisation",
    label: "Hospitalisation",
    path: "/hospitalisation",
    icon: Hospital,
    roles: ["ADMIN", "MEDECIN", "HOSPITALISATION"],
  },
  {
    id: "paiement",
    label: "Paiement & facturation",
    path: "/paiement",
    icon: CreditCard,
    roles: ["ADMIN", "CAISSIER"],
  },
  {
    id: "consultation",
    label: "Consultation",
    path: "/consultation",
    icon: Stethoscope,
    roles: ["ADMIN", "MEDECIN"],
  },
  {
    id: "laboratoire",
    label: "Laboratoire",
    path: "/laboratoire",
    icon: FlaskConical,
    roles: ["ADMIN", "LABORATOIRE", "MEDECIN"],
  },
  {
    id: "pharmacie",
    label: "Pharmacie, stock & logistique",
    path: "/pharmacie",
    icon: Pill,
    roles: ["ADMIN", "PHARMACIEN"],
  },
  {
    id: "maternite",
    label: "Maternité",
    path: "/maternite",
    icon: Baby,
    roles: ["ADMIN", "MEDECIN", "MATERNITE"],
  },
  {
    id: "rendezvous",
    label: "Rendez-vous & agenda",
    path: "/rendez-vous",
    icon: CalendarDays,
    roles: ["ADMIN", "ACCUEIL", "MEDECIN", "RENDEZ_VOUS"],
  },
  {
    id: "auth",
    label: "Utilisateurs & notifications",
    path: "/administration",
    icon: ShieldCheck,
    roles: ["ADMIN"],
  },
  {
    id: "bi",
    label: "BI & statistiques",
    path: "/statistiques",
    icon: BarChart3,
    roles: ["ADMIN", "DIRECTION"],
  },
  {
    id: "chatbot",
    label: "Assistant intelligent",
    path: "/assistant",
    icon: MessageCircleMore,
    roles: ["ALL"],
  },
];
