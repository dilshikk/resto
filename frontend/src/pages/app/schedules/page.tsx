import { useState, type FormEvent } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import axios from "axios";
import { CalendarClock, Pause, Play, Pencil, Trash2, Plus, Clock } from "lucide-react";
import { listTemplates } from "@/api/checklists.ts";
import { listBranches } from "@/api/branches.ts";
import {
  listSchedules,
  createSchedules,
  updateSchedule,
  deleteSchedule,
  scheduleToUpdate,
} from "@/api/schedules.ts";
import type { Schedule, ScheduleUpdate } from "@/api/schedules.ts";
import { cn } from "@/lib/utils.ts";

const WEEKDAYS = [
  { value: 1, label: "Пн" },
  { value: 2, label: "Вт" },
  { value: 3, label: "Ср" },
  { value: 4, label: "Чт" },
  { value: 5, label: "Пт" },
  { value: 6, label: "Сб" },
  { value: 7, label: "Вс" },
];

const SHIFTS = [
  { value: "morning", label: "Утро" },
  { value: "afternoon", label: "День" },
  { value: "evening", label: "Вечер" },
];

const INPUT =
  "w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring";

function fmtDate(d: string | null) {
  if (!d) return "без конца";
  const [y, m, day] = d.split("-");
  return `${day}.${m}.${y}`;
}

function errorMessage(err: unknown, fallback: string) {
  if (axios.isAxiosError(err)) {
    const detail: unknown = err.response?.data?.detail;
    if (typeof detail === "string") return detail;
  }
  return fallback;
}

function todayStr() {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

type FormState = {
  template_id: string;
  branch_ids: number[];
  shift: string;
  start_date: string;
  end_date: string;
  weekdays: number[];
  window_start: string;
  window_end: string;
};

function ScheduleModal({ editing, onClose }: { editing: Schedule | null; onClose: () => void }) {
  const qc = useQueryClient();
  const { data: templates } = useQuery({ queryKey: ["templates"], queryFn: listTemplates });
  const { data: branches } = useQuery({ queryKey: ["branches"], queryFn: listBranches });

  const [form, setForm] = useState<FormState>(
    editing
      ? {
          template_id: String(editing.template_id),
          branch_ids: [editing.branch_id],
          shift: editing.shift,
          start_date: editing.start_date,
          end_date: editing.end_date ?? "",
          weekdays: editing.weekdays,
          window_start: editing.window_start.slice(0, 5),
          window_end: editing.window_end.slice(0, 5),
        }
      : {
          template_id: "",
          branch_ids: [],
          shift: "morning",
          start_date: todayStr(),
          end_date: "",
          weekdays: [1, 2, 3, 4, 5, 6, 7],
          window_start: "07:00",
          window_end: "07:50",
        },
  );

  const mut = useMutation({
    mutationFn: async () => {
      const fields = {
        template_id: Number(form.template_id),
        shift: form.shift,
        start_date: form.start_date,
        end_date: form.end_date || null,
        weekdays: form.weekdays,
        window_start: form.window_start,
        window_end: form.window_end,
      };
      if (editing) {
        await updateSchedule(editing.id, {
          ...fields,
          branch_id: form.branch_ids[0],
          is_active: editing.is_active,
        });
      } else {
        await createSchedules({ ...fields, branch_ids: form.branch_ids });
      }
    },
    onSuccess: () => {
      toast.success(editing ? "Расписание обновлено" : "Расписание создано");
      qc.invalidateQueries({ queryKey: ["schedules"] });
      onClose();
    },
    onError: (err) => toast.error(errorMessage(err, "Не удалось сохранить расписание")),
  });

  const toggleBranch = (id: number) =>
    setForm((f) => {
      if (editing) return { ...f, branch_ids: [id] };
      return {
        ...f,
        branch_ids: f.branch_ids.includes(id) ? f.branch_ids.filter((b) => b !== id) : [...f.branch_ids, id],
      };
    });

  const toggleDay = (d: number) =>
    setForm((f) => ({
      ...f,
      weekdays: f.weekdays.includes(d) ? f.weekdays.filter((x) => x !== d) : [...f.weekdays, d].sort(),
    }));

  const canSubmit =
    form.template_id !== "" && form.branch_ids.length > 0 && form.weekdays.length > 0 && !mut.isPending;

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (canSubmit) mut.mutate();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-lg rounded-2xl border bg-card shadow-xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between border-b px-5 py-4">
          <h2 className="text-lg font-semibold">{editing ? "Изменить расписание" : "Создать расписание"}</h2>
          <button type="button" onClick={onClose} className="cursor-pointer text-xl text-muted-foreground hover:text-foreground">
            ✕
          </button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4 p-5">
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Шаблон</label>
            <select
              className={INPUT}
              value={form.template_id}
              onChange={(e) => setForm((f) => ({ ...f, template_id: e.target.value }))}
              required
            >
              <option value="">Выберите шаблон</option>
              {templates?.map((t) => (
                <option key={t.id} value={String(t.id)}>{t.name}</option>
              ))}
            </select>
          </div>

          <div className="space-y-1.5">
            <label className="text-sm font-medium">{editing ? "Филиал" : "Филиалы"}</label>
            <div className="flex flex-wrap gap-1.5">
              {branches?.map((b) => {
                const active = form.branch_ids.includes(b.id);
                return (
                  <button
                    key={b.id}
                    type="button"
                    onClick={() => toggleBranch(b.id)}
                    className={cn(
                      "cursor-pointer rounded-full border px-3 py-1 text-xs font-medium transition-colors",
                      active ? "border-primary bg-primary text-primary-foreground" : "hover:bg-muted",
                    )}
                  >
                    {b.name}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <label className="text-sm font-medium">С даты</label>
              <input
                type="date"
                className={INPUT}
                value={form.start_date}
                onChange={(e) => setForm((f) => ({ ...f, start_date: e.target.value }))}
                required
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium">По дату</label>
              <input
                type="date"
                className={INPUT}
                value={form.end_date}
                min={form.start_date}
                onChange={(e) => setForm((f) => ({ ...f, end_date: e.target.value }))}
              />
              <p className="text-xs text-muted-foreground">Пусто — без конца</p>
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-sm font-medium">Дни недели</label>
            <div className="flex flex-wrap gap-1.5">
              {WEEKDAYS.map((d) => {
                const active = form.weekdays.includes(d.value);
                return (
                  <button
                    key={d.value}
                    type="button"
                    onClick={() => toggleDay(d.value)}
                    className={cn(
                      "size-9 cursor-pointer rounded-lg border text-xs font-semibold transition-colors",
                      active ? "border-primary bg-primary text-primary-foreground" : "hover:bg-muted",
                    )}
                  >
                    {d.label}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Открывается</label>
              <input
                type="time"
                className={INPUT}
                value={form.window_start}
                onChange={(e) => setForm((f) => ({ ...f, window_start: e.target.value }))}
                required
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Закрывается</label>
              <input
                type="time"
                className={INPUT}
                value={form.window_end}
                onChange={(e) => setForm((f) => ({ ...f, window_end: e.target.value }))}
                required
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Смена</label>
              <select
                className={INPUT}
                value={form.shift}
                onChange={(e) => setForm((f) => ({ ...f, shift: e.target.value }))}
              >
                {SHIFTS.map((s) => (
                  <option key={s.value} value={s.value}>{s.label}</option>
                ))}
              </select>
            </div>
          </div>
          <p className="text-xs text-muted-foreground">
            Время — местное время филиала. Должности берутся из шаблона. После окончания окна чек-лист
            считается просроченным и срабатывают уведомления руководителям.
          </p>

          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="cursor-pointer rounded-lg px-4 py-2 text-sm hover:bg-muted">
              Отмена
            </button>
            <button
              type="submit"
              disabled={!canSubmit}
              className="cursor-pointer rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90 disabled:opacity-50"
            >
              {mut.isPending ? "Сохраняем..." : "Сохранить"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function ScheduleCard({ s, onEdit }: { s: Schedule; onEdit: () => void }) {
  const qc = useQueryClient();
  const [confirmDelete, setConfirmDelete] = useState(false);

  const toggleMut = useMutation({
    mutationFn: () => updateSchedule(s.id, scheduleToUpdate(s, { is_active: !s.is_active } satisfies Partial<ScheduleUpdate>)),
    onSuccess: () => {
      toast.success(s.is_active ? "Расписание на паузе" : "Расписание возобновлено");
      qc.invalidateQueries({ queryKey: ["schedules"] });
    },
    onError: (err) => toast.error(errorMessage(err, "Не удалось изменить статус")),
  });

  const deleteMut = useMutation({
    mutationFn: () => deleteSchedule(s.id),
    onSuccess: () => {
      toast.success("Расписание удалено");
      qc.invalidateQueries({ queryKey: ["schedules"] });
    },
    onError: (err) => toast.error(errorMessage(err, "Не удалось удалить")),
  });

  return (
    <div className={cn("rounded-xl border bg-card p-4 space-y-3", !s.is_active && "opacity-60")}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate font-semibold">{s.template_name}</p>
          <p className="truncate text-sm text-muted-foreground">{s.branch_name}</p>
        </div>
        <span
          className={cn(
            "shrink-0 rounded-full px-2.5 py-0.5 text-xs font-medium",
            s.is_active ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground",
          )}
        >
          {s.is_active ? "Активно" : "Пауза"}
        </span>
      </div>

      <div className="flex items-center gap-2 text-lg font-bold tabular-nums">
        <Clock className="size-4 text-muted-foreground" />
        {s.window_start.slice(0, 5)}–{s.window_end.slice(0, 5)}
      </div>

      <p className="text-sm text-muted-foreground">
        {fmtDate(s.start_date)} — {fmtDate(s.end_date)}
      </p>

      <div className="flex flex-wrap gap-1">
        {WEEKDAYS.map((d) => (
          <span
            key={d.value}
            className={cn(
              "rounded px-1.5 py-0.5 text-[11px] font-semibold",
              s.weekdays.includes(d.value) ? "bg-secondary text-secondary-foreground" : "text-muted-foreground/40",
            )}
          >
            {d.label}
          </span>
        ))}
      </div>

      <div className="flex gap-1 border-t pt-3">
        <button
          type="button"
          onClick={() => toggleMut.mutate()}
          disabled={toggleMut.isPending}
          className="flex cursor-pointer items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm hover:bg-muted disabled:opacity-50"
        >
          {s.is_active ? <Pause className="size-3.5" /> : <Play className="size-3.5" />}
          {s.is_active ? "Пауза" : "Возобновить"}
        </button>
        <button
          type="button"
          onClick={onEdit}
          className="flex cursor-pointer items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm hover:bg-muted"
        >
          <Pencil className="size-3.5" />
          Изменить
        </button>
        <button
          type="button"
          onClick={() => (confirmDelete ? deleteMut.mutate() : setConfirmDelete(true))}
          onBlur={() => setConfirmDelete(false)}
          disabled={deleteMut.isPending}
          className="ml-auto flex cursor-pointer items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm text-destructive hover:bg-muted disabled:opacity-50"
        >
          <Trash2 className="size-3.5" />
          {confirmDelete ? "Точно удалить?" : "Удалить"}
        </button>
      </div>
    </div>
  );
}

export default function SchedulesPage() {
  const [modal, setModal] = useState<{ editing: Schedule | null } | null>(null);
  const { data: schedules, isLoading, isError } = useQuery({
    queryKey: ["schedules"],
    queryFn: listSchedules,
  });

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4 md:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Расписание</h1>
          <p className="text-sm text-muted-foreground">
            Создайте один раз — чек-листы будут появляться автоматически в нужное время.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setModal({ editing: null })}
          className="flex cursor-pointer items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90"
        >
          <Plus className="size-4" />
          Создать расписание
        </button>
      </div>

      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-52 animate-pulse rounded-xl bg-muted" />
          ))}
        </div>
      ) : isError ? (
        <div className="rounded-xl border border-dashed p-10 text-center text-sm text-muted-foreground">
          Не удалось загрузить расписания. Обновите страницу.
        </div>
      ) : !schedules || schedules.length === 0 ? (
        <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed p-12 text-center">
          <CalendarClock className="size-10 text-muted-foreground" />
          <p className="font-semibold">Расписаний пока нет</p>
          <p className="max-w-sm text-sm text-muted-foreground">
            Например: «Утренний чек-лист» с 01 по 31 января, каждый день с 07:00 до 07:50.
          </p>
          <button
            type="button"
            onClick={() => setModal({ editing: null })}
            className="cursor-pointer rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:opacity-90"
          >
            Создать расписание
          </button>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {schedules.map((s) => (
            <ScheduleCard key={s.id} s={s} onEdit={() => setModal({ editing: s })} />
          ))}
        </div>
      )}

      {modal && <ScheduleModal editing={modal.editing} onClose={() => setModal(null)} />}
    </div>
  );
}
