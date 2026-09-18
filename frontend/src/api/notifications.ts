import { apiClient } from "./client.ts";

export type Notification = {
  id: number;
  type: "reminder" | "overdue" | "escalation" | "issue_assigned";
  title: string;
  message?: string;
  is_read: boolean;
  created_at: string;
};

export async function listNotifications(unreadOnly?: boolean): Promise<Notification[]> {
  const res = await apiClient.get<Notification[]>("/notifications", {
    params: unreadOnly ? { unread_only: true } : undefined,
  });
  return res.data;
}

export async function getUnreadCount(): Promise<number> {
  const res = await apiClient.get<{ count: number }>("/notifications/unread-count");
  return res.data.count;
}

export async function markNotificationRead(id: number): Promise<void> {
  await apiClient.post(`/notifications/${id}/read`);
}

export async function markAllNotificationsRead(): Promise<void> {
  await apiClient.post("/notifications/read-all");
}
