import type {
  HospitalNotification,
  NotificationKind,
  NotificationRecipientType,
} from "../types/administration";

const STORAGE_KEY =
  "hospitalis_notifications";

function loadNotifications():
  HospitalNotification[] {
  const stored =
    localStorage.getItem(
      STORAGE_KEY
    );

  if (!stored) {
    return [];
  }

  try {
    return JSON.parse(
      stored
    ) as HospitalNotification[];
  } catch {
    return [];
  }
}

function saveNotifications(
  notifications:
    HospitalNotification[]
) {
  localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify(
      notifications
    )
  );
}

export async function createNotification(
  input: {
    recipientType:
      NotificationRecipientType;

    recipientKey: string;

    kind:
      NotificationKind;

    title: string;
    message: string;

    actionPath?: string;
  }
): Promise<HospitalNotification> {
  const notifications =
    loadNotifications();

  const notification:
    HospitalNotification = {
    id:
      crypto.randomUUID(),

    recipientType:
      input.recipientType,

    recipientKey:
      input.recipientKey,

    kind:
      input.kind,

    title:
      input.title,

    message:
      input.message,

    actionPath:
      input.actionPath,

    read:
      false,

    createdAt:
      new Date().toISOString(),
  };

  notifications.unshift(
    notification
  );

  saveNotifications(
    notifications
  );

  return notification;
}

export async function listNotifications(
  recipientType:
    NotificationRecipientType,
  recipientKey: string
): Promise<HospitalNotification[]> {
  return loadNotifications()
    .filter(
      notification =>
        notification.recipientType ===
          recipientType &&
        (
          notification.recipientKey ===
            recipientKey ||
          notification.recipientKey ===
            "ALL"
        )
    )
    .sort(
      (a, b) =>
        b.createdAt.localeCompare(
          a.createdAt
        )
    );
}

export async function listUnreadNotifications(
  recipientType:
    NotificationRecipientType,
  recipientKey: string
): Promise<HospitalNotification[]> {
  return (
    await listNotifications(
      recipientType,
      recipientKey
    )
  ).filter(
    notification =>
      !notification.read
  );
}

export async function markNotificationRead(
  notificationId: string
): Promise<void> {
  const notifications =
    loadNotifications();

  const index =
    notifications.findIndex(
      notification =>
        notification.id ===
        notificationId
    );

  if (index === -1) {
    return;
  }

  notifications[index] = {
    ...notifications[index],

    read:
      true,

    readAt:
      new Date().toISOString(),
  };

  saveNotifications(
    notifications
  );
}

export async function markAllNotificationsRead(
  recipientType:
    NotificationRecipientType,
  recipientKey: string
): Promise<void> {
  const notifications =
    loadNotifications();

  const now =
    new Date().toISOString();

  const updated =
    notifications.map(
      notification => {
        if (
          notification.recipientType !==
            recipientType ||
          (
            notification.recipientKey !==
              recipientKey &&
            notification.recipientKey !==
              "ALL"
          ) ||
          notification.read
        ) {
          return notification;
        }

        return {
          ...notification,

          read:
            true,

          readAt:
            now,
        };
      }
    );

  saveNotifications(
    updated
  );
}
