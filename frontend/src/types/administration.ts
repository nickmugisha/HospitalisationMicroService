export type HospitalUserRole =
  | "ADMIN"
  | "RECEPTION"
  | "DOCTOR"
  | "NURSE"
  | "LAB_TECH"
  | "PHARMACIST"
  | "BILLING"
  | "MATERNITY"
  | "MANAGER";

export interface HospitalUser {
  id: string;

  fullName: string;
  username: string;

  email: string;
  phone: string;

  role: HospitalUserRole;
  department: string;

  active: boolean;

  createdAt: string;
  updatedAt: string;
}

export type NotificationRecipientType =
  | "PATIENT"
  | "STAFF";

export type NotificationKind =
  | "APPOINTMENT_REQUEST"
  | "APPOINTMENT_APPROVED"
  | "APPOINTMENT_REJECTED"
  | "APPOINTMENT_REMINDER"
  | "SYSTEM";

export interface HospitalNotification {
  id: string;

  recipientType:
    NotificationRecipientType;

  recipientKey: string;

  kind: NotificationKind;

  title: string;
  message: string;

  read: boolean;

  actionPath?: string;

  createdAt: string;
  readAt?: string;
}
