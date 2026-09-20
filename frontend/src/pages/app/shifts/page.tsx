import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  listShifts,
  createShift,
  updateShift,
} from "@/api/shifts.ts";
import type { Shift, ShiftCreate, ShiftStatus } from "@/api/shifts.ts";
import { listEmployees } from "@/api/employees.ts";
import { listBranches } from "@/api/branches.ts";
import { CalendarDays, Plus, Pencil } from "lucide-react";
import { cn } from "@/lib/utils.ts";

const STATUS_CONFIG: Record<ShiftStatus, { label: string; color: string }> = {
  planned: { label: "Запланирована", color: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400" },
  active: { label: "Активна", color: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400" },
  completed: { label: "Завершена", color: "bg-secondary text-secondary-foreground" },
  no_show: { label: "Не явился", color: "bg-destructive/15 text-destructive" },
};

function today() {
  return new Date().toISOString().slice(0, 10);
}

// ── Create Shift Modal ────────────────────────────────────────────────────

function CreateShiftModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const { data: employees } = useQuery({ queryKey: ["employees"], queryFn: () => listEmployees() });
  const { data: branches } = useQuery({ queryKey: ["branches"], queryFn: listBranches });

  const [form, setForm] = useState<ShiftCreate>({
    employee_id: 0,
    branch_id: 0,
    shift_date: today(),
    starts_at: "09:00",
    ends_at: "21:00",
  });

  const mut = useMutation({
    mutationFn: (d: ShiftCreate) => createShift(d),
    onSuccess: () => {
      toast.success("Смена создана");
      qc.invalidateQueries({ queryKey: ["shifts"] });
      onClose();
    },
    onError: () => toast.error("Не удалось создать смену"),
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.employee_id || !form.branch_id) {
      toast.error("Выберите сотрудника и филиал");
      return;
    }
    mut.mutate(form);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-md rounded-2xl border bg-card shadow-xl">
        <div className="flex items-center justify-between border-b px-5 py-4">
          <h2 className="text-lg font-semibold">Новая смена</h2>
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground text-xl">✕</button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4 p-5">
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Сотрудник</label>
            <select
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
              value={form.employee_id || ""}
              onChange={(e) => setForm((f) => ({ ...f, employee_id: Number(e.target.value) }))}
              required
            >
              <option value="">Выберите сотрудника</option>
              {employees?.filter((emp) => emp.status === "active").map((emp) => (
                <option key={emp.id} value={emp.id}>{emp.full_name} — {emp.role_name}</option>
              ))}
            </select>
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Филиал</label>
            <select
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
              value={form.branch_id || ""}
              onChange={(e) => setForm((f) => ({ ...f, branch_id: Number(e.target.value) }))}
              required
            >
              <option value="">Выберите филиал</option>
              {branches?.map((b) => (
                <option key={b.id} value={b.id}>{b.name}</option>
              ))}
            </select>
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Дата</label>
            <input
              type="date"
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
              value={form.shift_date}
              onChange={(e) => setForm((f) => ({ ...f, shift_date: e.target.value }))}
              required
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Начало</label>
              <input
                type="time"
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
                value={form.starts_at}
                onChange={(e) => setForm((f) => ({ ...f, starts_at: e.target.value }))}
                required
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Конец</label>
              <input
                type="time"
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
                value={form.ends_at}
                onChange={(e) => setForm((f) => ({ ...f, ends_at: e.target.value }))}
                required
              />
            </div>
          </div>
          <div className="flex gap-2 justify-end pt-2">
            <button type="button" onClick={onClose} className="rounded-lg border px-4 py-2 text-sm hover:bg-muted">Отмена</button>
            <button
              type="submit"
              disabled={mut.isPending}
              className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90 disabled:opacity-50"
            >
              {mut.isPending ? "Создаём..." : "Создать"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Edit Status Modal ────────────────────────────────────────────────────

function EditShiftModal({ shift, onClose }: { shift: Shift; onClose: () => void }) {
  const qc = useQueryClient();
  const [status, setStatus] = useState<ShiftStatus>(shift.status);
  const [startsAt, setStartsAt] = useState(shift.starts_at);
  const [endsAt, setEndsAt] = useState(shift.ends_at);

  const mut = useMutation({
    mutationFn: () => updateShift(shift.id, { status, starts_at: startsAt, ends_at: endsAt }),
    onSuccess: () => {
      toast.success("Смена обновлена");
      qc.invalidateQueries({ queryKey: ["shifts"] });
      onClose();
    },
    onError: () => toast.error("Не удалось обновить смену"),
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-sm rounded-2xl border bg-card shadow-xl">
        <div className="flex items-center justify-between border-b px-5 py-4">
          <h2 className="text-lg font-semibold">Изменить смену</h2>
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground text-xl">✕</button>
        </div>
        <form
          onSubmit={(e) => { e.preventDefault(); mut.mutate(); }}
          className="space-y-4 p-5"
        >
          <p className="text-sm text-muted-foreground">
            {shift.employee_name} · {shift.shift_date}
          </p>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Начало</label>
              <input
                type="time"
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
                value={startsAt}
                onChange={(e) => setStartsAt(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Конец</label>
              <input
                type="time"
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
                value={endsAt}
                onChange={(e) => setEndsAt(e.target.value)}
              />
            </div>
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Статус</label>
            <select
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
              value={status}
              onChange={(e) => setStatus(e.target.value as ShiftStatus)}
            >
              {(Object.keys(STATUS_CONFIG) as ShiftStatus[]).map((s) => (
                <option key={s} value={s}>{STATUS_CONFIG[s].label}</option>
              ))}
            </select>
          </div>
          <div className="flex gap-2 justify-end">
            <button type="button" onClick={onClose} className="rounded-lg border px-4 py-2 text-sm hover:bg-muted">Отмена</button>
            <button
              type="submit"
              disabled={mut.isPending}
              className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90 disabled:opacity-50"
            >
              {mut.isPending ? "Сохраняем..." : "Сохранить"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────

export default function ShiftsPage() {
  const [filterDate, setFilterDate] = useState(today());
  const [createOpen, setCreateOpen] = useState(false);
  const [editingShift, setEditingShift] = useState<Shift | null>(null);

  const { data: shifts, isLoading } = useQuery({
    queryKey: ["shifts", filterDate],
    queryFn: () => listShifts({ shift_date: filterDate }),
  });

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-4 md:p-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Смены</h1>
          <p className="text-sm text-muted-foreground">Расписание и статусы смен сотрудников</p>
        </div>
        <button
          type="button"
          onClick={() => setCreateOpen(true)}
          className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90"
        >
          <Plus className="size-4" />Новая смена
        </button>
      </div>

      {/* Date filter */}
      <div className="flex items-center gap-3">
        <label className="text-sm font-medium text-muted-foreground">Дата:</label>
        <input
          type="date"
          className="rounded-lg border bg-background px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-ring"
          value={filterDate}
          onChange={(e) => setFilterDate(e.target.value)}
        />
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-14 animate-pulse rounded-xl border bg-muted" />
          ))}
        </div>
      ) : !shifts || shifts.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed py-16 text-center">
          <CalendarDays className="size-10 text-muted-foreground" />
          <p className="font-semibold">Нет смен на выбранную дату</p>
          <p className="text-sm text-muted-foreground">Создайте смену, нажав кнопку «Новая смена»</p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border">
          <table className="w-full text-sm">
            <thead className="bg-muted/50">
              <tr>
                <th className="px-4 py-3 text-left font-medium">Сотрудник</th>
                <th className="px-4 py-3 text-left font-medium">Филиал</th>
                <th className="px-4 py-3 text-left font-medium">Время</th>
                <th className="px-4 py-3 text-left font-medium">Статус</th>
                <th className="px-4 py-3 text-right font-medium">Действия</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {shifts.map((shift) => (
                <tr key={shift.id} className="hover:bg-muted/30">
                  <td className="px-4 py-3 font-medium">{shift.employee_name}</td>
                  <td className="px-4 py-3 text-muted-foreground">{shift.branch_name}</td>
                  <td className="px-4 py-3 text-muted-foreground tabular-nums">
                    {shift.starts_at} – {shift.ends_at}
                  </td>
                  <td className="px-4 py-3">
                    <span className={cn(
                      "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
                      STATUS_CONFIG[shift.status].color,
                    )}>
                      {STATUS_CONFIG[shift.status].label}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      type="button"
                      onClick={() => setEditingShift(shift)}
                      className="rounded p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
                      title="Редактировать"
                    >
                      <Pencil className="size-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {createOpen && <CreateShiftModal onClose={() => setCreateOpen(false)} />}
      {editingShift && (
        <EditShiftModal shift={editingShift} onClose={() => setEditingShift(null)} />
      )}
    </div>
  );
}
