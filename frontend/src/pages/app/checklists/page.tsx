import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  listChecklists,
  getChecklist,
  createChecklist,
  toggleChecklistItem,
  completeChecklist,
  listTemplates,
} from "@/api/checklists.ts";
import type { Checklist, ChecklistCreate } from "@/api/checklists.ts";
import { listBranches } from "@/api/branches.ts";
import { getMyProfile } from "@/api/employees.ts";
import { CheckSquare, Plus, Clock } from "lucide-react";
import { cn } from "@/lib/utils.ts";

const SHIFTS = [
  { value: "morning", label: "Утренняя" },
  { value: "afternoon", label: "Дневная" },
  { value: "evening", label: "Вечерняя" },
];

function todayDate() {
  return new Date().toISOString().slice(0, 10);
}

// ── Progress Bar ──────────────────────────────────────────────────────────

function ProgressBar({ total, done }: { total: number; done: number }) {
  const pct = total === 0 ? 0 : Math.round((done / total) * 100);
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>{done} из {total}</span>
        <span>{pct}%</span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <div
          className={cn(
            "h-full rounded-full transition-all duration-300",
            pct === 100 ? "bg-green-500" : "bg-primary",
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

// ── Checklist Card ────────────────────────────────────────────────────────

function ChecklistCard({ cl, onClick }: { cl: Checklist; onClick: () => void }) {
  const shiftLabel = SHIFTS.find((s) => s.value === cl.shift)?.label ?? cl.shift;
  const isComplete = cl.status === "completed";

  return (
    <button
      type="button"
      onClick={onClick}
      className="w-full cursor-pointer text-left space-y-3 rounded-xl border bg-card p-4 shadow-sm transition-all hover:border-primary/40 hover:shadow-md"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="font-semibold truncate">{cl.template_name}</p>
          <p className="text-sm text-muted-foreground truncate">{cl.branch_name}</p>
        </div>
        <span
          className={cn(
            "shrink-0 inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
            isComplete
              ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400"
              : "bg-secondary text-secondary-foreground",
          )}
        >
          {isComplete ? "Завершён" : "Открыт"}
        </span>
      </div>
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <Clock className="size-3.5" />
        <span>{shiftLabel}</span>
        <span>·</span>
        <span>{cl.date}</span>
      </div>
      <ProgressBar total={cl.total_items} done={cl.completed_items} />
    </button>
  );
}

// ── Checklist Detail Modal ────────────────────────────────────────────────

function ChecklistDetailModal({
  checklistId,
  isManager,
  onClose,
}: {
  checklistId: number;
  isManager: boolean;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const { data: detail, isLoading } = useQuery({
    queryKey: ["checklist", checklistId],
    queryFn: () => getChecklist(checklistId),
  });

  const toggleMut = useMutation({
    mutationFn: (itemId: number) => toggleChecklistItem(checklistId, itemId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["checklist", checklistId] });
      qc.invalidateQueries({ queryKey: ["checklists"] });
    },
    onError: () => toast.error("Не удалось обновить пункт"),
  });

  const completeMut = useMutation({
    mutationFn: () => completeChecklist(checklistId),
    onSuccess: () => {
      toast.success("Чек-лист завершён");
      qc.invalidateQueries({ queryKey: ["checklist", checklistId] });
      qc.invalidateQueries({ queryKey: ["checklists"] });
      onClose();
    },
    onError: () => toast.error("Не удалось завершить чек-лист"),
  });

  const allRequiredDone =
    detail ? detail.items.filter((i) => i.is_required).every((i) => i.is_completed) : false;
  const isOpen = detail?.status === "open";

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 sm:items-center sm:p-4">
      <div className="flex w-full max-h-[90vh] flex-col overflow-hidden rounded-t-2xl border bg-card shadow-xl sm:max-w-lg sm:rounded-2xl">
        {/* Header */}
        <div className="flex shrink-0 items-center justify-between border-b px-5 py-4">
          <div className="min-w-0">
            <h2 className="font-semibold truncate">{detail?.template_name ?? "..."}</h2>
            {detail && (
              <p className="text-sm text-muted-foreground">
                {detail.branch_name} · {SHIFTS.find((s) => s.value === detail.shift)?.label}
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="ml-2 shrink-0 text-muted-foreground hover:text-foreground text-xl"
          >
            ✕
          </button>
        </div>

        {/* Progress bar */}
        {detail && (
          <div className="shrink-0 border-b bg-muted/30 px-5 py-3">
            <ProgressBar total={detail.total_items} done={detail.completed_items} />
          </div>
        )}

        {/* Items */}
        {isLoading ? (
          <div className="flex flex-1 items-center justify-center p-8">
            <div className="h-8 w-32 animate-pulse rounded-lg bg-muted" />
          </div>
        ) : detail && detail.items.length > 0 ? (
          <div className="flex-1 divide-y overflow-y-auto">
            {detail.items.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => {
                  if (!isOpen || toggleMut.isPending) return;
                  toggleMut.mutate(item.id);
                }}
                disabled={!isOpen || toggleMut.isPending}
                className={cn(
                  "w-full px-5 py-3.5 text-left transition-colors flex items-start gap-3",
                  isOpen && "cursor-pointer hover:bg-muted/40",
                  !isOpen && "cursor-default",
                )}
              >
                {/* Circle checkbox */}
                <div
                  className={cn(
                    "mt-0.5 shrink-0 size-5 rounded-full border-2 flex items-center justify-center transition-colors",
                    item.is_completed
                      ? "border-green-500 bg-green-500"
                      : "border-muted-foreground/30",
                  )}
                >
                  {item.is_completed && (
                    <svg
                      className="size-3 text-white"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      strokeWidth={3}
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                  )}
                </div>

                <div className="flex-1 min-w-0">
                  <p
                    className={cn(
                      "text-sm font-medium",
                      item.is_completed && "text-muted-foreground line-through",
                    )}
                  >
                    {item.title}
                    {item.is_required && !item.is_completed && (
                      <span className="ml-1.5 text-xs text-destructive">*</span>
                    )}
                  </p>
                  {item.is_completed && item.completed_by_name && (
                    <p className="mt-0.5 text-xs text-muted-foreground">{item.completed_by_name}</p>
                  )}
                </div>
              </button>
            ))}
          </div>
        ) : (
          <div className="flex flex-1 items-center justify-center p-8 text-center">
            <p className="text-sm text-muted-foreground">Нет пунктов в этом чек-листе</p>
          </div>
        )}

        {/* Complete button */}
        {isOpen && isManager && allRequiredDone && (
          <div className="shrink-0 border-t p-4">
            <button
              type="button"
              onClick={() => completeMut.mutate()}
              disabled={completeMut.isPending}
              className="w-full rounded-lg bg-green-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-green-700 disabled:opacity-50"
            >
              {completeMut.isPending ? "Завершаем..." : "Завершить чек-лист"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Create Checklist Modal ────────────────────────────────────────────────

function CreateChecklistModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const { data: templates } = useQuery({ queryKey: ["templates"], queryFn: listTemplates });
  const { data: branches } = useQuery({ queryKey: ["branches"], queryFn: listBranches });

  const [form, setForm] = useState<ChecklistCreate>({
    template_id: 0,
    branch_id: 0,
    shift: "morning",
    date: todayDate(),
  });

  const mut = useMutation({
    mutationFn: (data: ChecklistCreate) => createChecklist(data),
    onSuccess: () => {
      toast.success("Чек-лист создан");
      qc.invalidateQueries({ queryKey: ["checklists"] });
      onClose();
    },
    onError: () => toast.error("Не удалось создать чек-лист"),
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.template_id || !form.branch_id) {
      toast.error("Выберите шаблон и филиал");
      return;
    }
    mut.mutate(form);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-md rounded-2xl border bg-card shadow-xl">
        <div className="flex items-center justify-between border-b px-5 py-4">
          <h2 className="text-lg font-semibold">Новый чек-лист</h2>
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground text-xl">✕</button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4 p-5">
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Шаблон</label>
            <select
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
              value={form.template_id || ""}
              onChange={(e) => setForm((f) => ({ ...f, template_id: Number(e.target.value) }))}
              required
            >
              <option value="">Выберите шаблон</option>
              {templates?.map((t) => (
                <option key={t.id} value={t.id}>{t.name}</option>
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
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Смена</label>
              <select
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
                value={form.shift}
                onChange={(e) => setForm((f) => ({ ...f, shift: e.target.value }))}
              >
                {SHIFTS.map((s) => (
                  <option key={s.value} value={s.value}>{s.label}</option>
                ))}
              </select>
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Дата</label>
              <input
                type="date"
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
                value={form.date}
                onChange={(e) => setForm((f) => ({ ...f, date: e.target.value }))}
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

// ── Page ──────────────────────────────────────────────────────────────────

export default function ChecklistsPage() {
  const [date, setDate] = useState(todayDate());
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [createOpen, setCreateOpen] = useState(false);

  const { data: profile } = useQuery({ queryKey: ["my-profile"], queryFn: getMyProfile });
  const isManager = (profile?.role_level ?? 0) >= 1;

  const { data: checklists, isLoading } = useQuery({
    queryKey: ["checklists", date],
    queryFn: () => listChecklists({ date }),
  });

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-4 md:p-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Чек-листы</h1>
          <p className="text-sm text-muted-foreground">Контроль выполнения стандартов</p>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className="rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
          />
          {isManager && (
            <button
              type="button"
              onClick={() => setCreateOpen(true)}
              className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90"
            >
              <Plus className="size-4" />Чек-лист
            </button>
          )}
        </div>
      </div>

      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-36 animate-pulse rounded-xl border bg-muted" />
          ))}
        </div>
      ) : !checklists || checklists.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed py-16 text-center">
          <CheckSquare className="size-10 text-muted-foreground" />
          <p className="font-semibold">Нет чек-листов за {date}</p>
          <p className="text-sm text-muted-foreground">
            {isManager ? "Создайте чек-лист для начала смены" : "Чек-листы для этой даты ещё не созданы"}
          </p>
          {isManager && (
            <button
              type="button"
              onClick={() => setCreateOpen(true)}
              className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90"
            >
              Создать чек-лист
            </button>
          )}
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {checklists.map((cl: Checklist) => (
            <ChecklistCard key={cl.id} cl={cl} onClick={() => setSelectedId(cl.id)} />
          ))}
        </div>
      )}

      {selectedId !== null && (
        <ChecklistDetailModal
          checklistId={selectedId}
          isManager={isManager}
          onClose={() => setSelectedId(null)}
        />
      )}
      {createOpen && <CreateChecklistModal onClose={() => setCreateOpen(false)} />}
    </div>
  );
}
