import { apiClient } from "./client.ts";

export type DeadlineMetrics = {
  on_time: number;
  overdue: number;
  not_completed: number;
  no_deadline: number;
  on_time_pct: number | null;
  avg_completion_minutes: number | null;
};

export type Summary = {
  date_from: string;
  date_to: string;
  total_checklists: number;
  completed_checklists: number;
  checklist_completion_pct: number;
  total_items: number;
  completed_items: number;
  item_completion_pct: number;
  missed_required_items: number;
  deadline: DeadlineMetrics;
};

export type DayPoint = {
  date: string;
  total: number;
  completed: number;
  pct: number;
  on_time: number;
  overdue: number;
  not_completed: number;
};

export type BranchRank = {
  branch_id: number;
  branch_name: string;
  total: number;
  completed: number;
  pct: number;
  on_time: number;
  overdue: number;
  not_completed: number;
};

export type Violation = {
  title: string;
  count: number;
};

type Params = { date_from?: string; date_to?: string; branch_id?: number };

export async function getSummary(p: Params): Promise<Summary> {
  const res = await apiClient.get<Summary>("/analytics/summary", { params: p });
  return res.data;
}

export async function getByDay(p: Params): Promise<DayPoint[]> {
  const res = await apiClient.get<DayPoint[]>("/analytics/by-day", { params: p });
  return res.data;
}

export async function getBranchesRanking(p: Omit<Params, "branch_id">): Promise<BranchRank[]> {
  const res = await apiClient.get<BranchRank[]>("/analytics/branches", { params: p });
  return res.data;
}

export async function getViolations(p: Params & { limit?: number }): Promise<Violation[]> {
  const res = await apiClient.get<Violation[]>("/analytics/violations", { params: p });
  return res.data;
}

export function buildExportUrl(p: Params): string {
  const base = import.meta.env.VITE_API_URL
    ? `${import.meta.env.VITE_API_URL}/api/v1`
    : "/api/v1";
  const params = new URLSearchParams();
  if (p.date_from) params.set("date_from", p.date_from);
  if (p.date_to) params.set("date_to", p.date_to);
  if (p.branch_id) params.set("branch_id", String(p.branch_id));
  return `${base}/analytics/export-csv?${params.toString()}`;
}
