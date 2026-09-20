import { useState, useEffect, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  listChecklists,
  getChecklist,
  createChecklist,
  toggleChecklistItem,
  skipChecklistItem,
  completeChecklist,
  listTemplates,
  getPhotoSignedUrl,
} from "@/api/checklists.ts";
import type { Checklist, ChecklistCreate, DeadlineStatus } from "@/api/checklists.ts";
import { listBranches } from "@/api/branches.ts";
import { getMyProfile } from "@/api/employees.ts";
import { listAuditLogs } from "@/api/audit-logs.ts";
import type { AuditLog } from "@/api/audit-logs.ts";
import {
  CheckSquare,
  Plus,
  Clock,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  History,
  SkipForward,
  ClipboardList,
  ImageOff,
} from "lucide-react";
import { cn } from "@/lib/utils.ts";

const SHIFTS = [
  { value: "morning", label: "Утренняя" },
  { value: "afternoon", label: "Дневная" },
  { value: "evening", label: "Вечерняя" },
];

function todayDate() {
  return new Date().toISOString().slice(0, 10);
}

// ── Deadline helpers ──────────────────────────────────────────────────────
//
// DeadlineStatus values come exclusively from the backend's
// _compute_deadline_status().  The frontend never re-derives them from
// due_at / completed_at to avoid divergence.
//
// The only client-side computation that remains is the live countdown
// timer (hh:mm:ss), which is purely presentational and cannot be
// moved server-side.

const DEADLINE_CONFIG: Record<
  NonNullable<DeadlineStatus>,
  { label: string; className: string; icon: React.ReactNode }
> = {
  ON_TIME: {
    label: "В срок",
    className: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
    icon: <CheckCircle2 className="size-3" />,
  },
  OVERDUE: {
    label: "Просрочено",
    className: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
    icon: <AlertTriangle className="size-3" />,
  },
  NOT_COMPLETED: {
    label: "Не выполнено",
    className: "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-400",
    icon: <XCircle className="size-3" />,
  },
};

// Inline text variants for the detail row (same source of truth).
const DEADLINE_INLINE: Record<NonNullable<DeadlineStatus>, { text: string; className: string }> = {
  ON_TIME: { text: "Выполнено в срок", className: "text-green-600 dark:text-green-400" },
  OVERDUE: { text: "Завершено с опозданием", className: "text-destructive" },
  NOT_COMPLETED: { text: "Не выполнено", className: "text-zinc-500 dark:text-zinc-400" },
};

/**
 * Live countdown hook — the only date arithmetic that stays on the client.
 * Returns remaining time formatted as "h:MM:SS" or "−h:MM:SS" (overdue).
 * Returns null while dueAt is absent or the component hasn't ticked yet.
 */
function useCountdown(dueAt: string | null | undefined): string | null {
  const [display, setDisplay] = useState<string | null>(null);

  useEffect(() => {
    if (!dueAt) return;

    const tick = () => {
      const diff = new Date(dueAt).getTime() - Date.now();
      const abs = Math.abs(diff);
      const h = Math.floor(abs / 3_600_000);
      const m = Math.floor((abs % 3_600_000) / 60_000);
      const s = Math.floor((abs % 60_000) / 1_000);
      const hPart = h > 0 ? `${h}:` : "";
      const formatted = `${hPart}${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
      setDisplay(diff < 0 ? `−${formatted}` : formatted);
    };

    tick();
    const id = setInterval(tick, 1_000);
    return () => clearInterval(id);
  }, [dueAt]);

  return display;
}

/**
 * Compact badge shown on checklist cards.
 *
 * Decision tree (mirrors backend _compute_deadline_status logic):
 *   1. No due_at → nothing.
 *   2. Backend supplied a terminal deadline_status → show status badge.
 *      (Covers: completed checklists, AND open ones that the server has
 *       already classified as OVERDUE or NOT_COMPLETED.)
 *   3. Open + no terminal status + countdown ticking → show live timer.
 */
function DeadlineBadge({ cl }: { cl: Checklist }) {
  // Only tick the timer when the checklist is open AND the backend hasn't
  // already classified it (i.e. deadline hasn't been definitively evaluated).
  const needsCountdown = cl.status === "open" && !cl.deadline_status;
  const countdown = useCountdown(needsCountdown ? cl.due_at : null);

  if (!cl.due_at) return null;

  // Backend has already classified this checklist — show the authoritative badge.
  if (cl.deadline_status) {
    const cfg = DEADLINE_CONFIG[cl.deadline_status];
    return (
      <span
        className={cn(
          "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
          cfg.className,
        )}
      >
        {cfg.icon}
        {cfg.label}
      </span>
    );
  }

  // Backend hasn't classified yet → show a live countdown.
  if (countdown !== null) {
    const isNegative = countdown.startsWith("−");
    return (
      <span
        className={cn(
          "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium tabular-nums",
          isNegative
            ? "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400"
            : "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400",
        )}
      >
        <Clock className="size-3" />
        {isNegative ? `Просрочено на ${countdown.slice(1)}` : `До дедлайна: ${countdown}`}
      </span>
    );
  }

  return null;
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
      <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
        <Clock className="size-3.5" />
        <span>{shiftLabel}</span>
        <span>·</span>
        <span>{cl.date}</span>
      </div>
      {/* Deadline badge / countdown */}
      <DeadlineBadge cl={cl} />
      <ProgressBar total={cl.total_items} done={cl.completed_items} />
    </button>
  );
}

// ── Audit Log helpers ─────────────────────────────────────────────────────

const ACTION_LABELS: Record<string, { label: string; color: string }> = {
  "checklist.created": { label: "Чек-лист создан", color: "text-blue-600 dark:text-blue-400" },
  "checklist.completed": { label: "Чек-лист завершён", color: "text-green-600 dark:text-green-400" },
  "task.completed": { label: "Пункт выполнен", color: "text-green-600 dark:text-green-400" },
  "task.reopened": { label: "Пункт переоткрыт", color: "text-amber-600 dark:text-amber-400" },
  "task.skipped": { label: "Пункт пропущен", color: "text-zinc-500 dark:text-zinc-400" },
  "photo.uploaded": { label: "Фото добавлено", color: "text-blue-600 dark:text-blue-400" },
  "photo.deleted": { label: "Фото удалено", color: "text-red-600 dark:text-red-400" },
};

function AuditLogTimeline({ logs }: { logs: AuditLog[] }) {
  if (logs.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 py-10 text-center">
        <History className="size-8 text-muted-foreground" />
        <p className="text-sm text-muted-foreground">История изменений пуста</p>
      </div>
    );
  }

  return (
    <ol className="relative border-l border-border ml-3 space-y-4 py-4 pr-2">
      {logs.map((log) => {
        const cfg = ACTION_LABELS[log.action] ?? { label: log.action, color: "text-foreground" };
        const timeStr = new Date(log.created_at).toLocaleString("ru-RU", {
          day: "2-digit",
          month: "2-digit",
          hour: "2-digit",
          minute: "2-digit",
        });
        const itemTitle = log.metadata?.title as string | undefined;
        return (
          <li key={log.id} className="ml-4">
            <div className="absolute -left-1.5 mt-1.5 h-3 w-3 rounded-full border border-border bg-background" />
            <div className="space-y-0.5">
              <p className={cn("text-sm font-medium", cfg.color)}>{cfg.label}</p>
              {itemTitle && (
                <p className="text-xs text-muted-foreground truncate">«{itemTitle}»</p>
              )}
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                {log.actor_name && <span>{log.actor_name}</span>}
                <span>{timeStr}</span>
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

// ── Signed photo image ────────────────────────────────────────────────────
//
// Browser <img src> cannot send Authorization headers.  Instead:
//   1. On mount, call GET /photos/{filename}/signed-url (Bearer via axios)
//      to obtain a short-lived (?token=…) URL.
//   2. Set that URL as the <img src>.
//   3. Cache the result in a module-level Map so sibling items that share
//      the same file don't re-fetch. Entries are evicted when they expire
//      (checked lazily on next access).

type SignedUrlCacheEntry = { url: string; expiresAt: number };
const signedUrlCache = new Map<string, SignedUrlCacheEntry>();

function SignedPhoto({
  rawUrl,
  alt,
  className,
}: {
  rawUrl: string;
  alt: string;
  className?: string;
}) {
  const [src, setSrc] = useState<string | null>(null);
  const [error, setError] = useState(false);
  // Stable ref to the raw URL so the effect dep doesn't change on re-renders.
  const rawUrlRef = useRef(rawUrl);
  rawUrlRef.current = rawUrl;

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      const cached = signedUrlCache.get(rawUrl);
      // Use cache if it won't expire within the next 60 s.
      if (cached && cached.expiresAt - Date.now() / 1000 > 60) {
        if (!cancelled) setSrc(cached.url);
        return;
      }

      try {
        const signedUrl = await getPhotoSignedUrl(rawUrl);
        // The backend also returns expires_at but getPhotoSignedUrl only
        // exposes the URL.  Parse the unix timestamp from the token query
        // param (?token={expires_unix}.{mac}) so we can cache correctly.
        const tokenMatch = signedUrl.match(/[?&]token=(\d+)\./);
        const expiresAt = tokenMatch ? parseInt(tokenMatch[1], 10) : Date.now() / 1000 + 3600;
        signedUrlCache.set(rawUrl, { url: signedUrl, expiresAt });
        if (!cancelled) setSrc(signedUrl);
      } catch {
        if (!cancelled) setError(true);
      }
    };

    load();
    return () => { cancelled = true; };
  }, [rawUrl]);

  if (error || (!src && rawUrl === "")) {
    return (
      <div className={cn("flex items-center justify-center bg-muted text-muted-foreground rounded", className)}>
        <ImageOff className="size-5" />
      </div>
    );
  }

  if (!src) {
    // Loading skeleton
    return <div className={cn("animate-pulse bg-muted rounded", className)} />;
  }

  return (
    <img
      src={src}
      alt={alt}
      className={cn("object-cover rounded", className)}
      onError={() => setError(true)}
    />
  );
}

// ── Checklist Detail Modal ────────────────────────────────────────────────

/**
 * Detailed deadline row shown inside the modal header.
 *
 * Shows the absolute due_at timestamp, then one of:
 *   - Live countdown (open + no terminal status from server yet)
 *   - Final server-side verdict text (OVERDUE / NOT_COMPLETED / ON_TIME)
 *
 * Like DeadlineBadge, this component never recomputes deadline_status
 * locally — it only reads the value supplied by the backend.
 */
function DeadlineDetailRow({ cl }: { cl: Checklist }) {
  const needsCountdown = cl.status === "open" && !cl.deadline_status;
  const countdown = useCountdown(needsCountdown ? cl.due_at : null);

  if (!cl.due_at) return null;

  const dueFormatted = new Date(cl.due_at).toLocaleString("ru-RU", {
    day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
  });

  return (
    <div className="shrink-0 border-b bg-muted/20 px-5 py-2.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
      <span>Дедлайн: <span className="font-medium text-foreground">{dueFormatted}</span></span>

      {/* Live countdown — only while the server hasn't classified yet */}
      {countdown !== null && (
        <span
          className={cn(
            "font-medium",
            countdown.startsWith("−")
              ? "text-destructive"
              : "text-amber-600 dark:text-amber-400",
          )}
        >
          {countdown.startsWith("−")
            ? `Просрочено на ${countdown.slice(1)}`
            : `Осталось: ${countdown}`}
        </span>
      )}

      {/* Terminal verdict from backend — single source of truth */}
      {cl.deadline_status && (
        <span className={cn("font-medium", DEADLINE_INLINE[cl.deadline_status].className)}>
          {DEADLINE_INLINE[cl.deadline_status].text}
        </span>
      )}
    </div>
  );
}

type ModalTab = "items" | "history";

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
  const [activeTab, setActiveTab] = useState<ModalTab>("items");
  const [skipNote, setSkipNote] = useState<Record<number, string>>({});

  const { data: detail, isLoading } = useQuery({
    queryKey: ["checklist", checklistId],
    queryFn: () => getChecklist(checklistId),
  });

  const { data: auditLogs, isLoading: logsLoading } = useQuery({
    queryKey: ["audit-logs", "checklist", checklistId],
    queryFn: () => listAuditLogs({ entity_type: "checklist", entity_id: checklistId, limit: 50 }),
    enabled: activeTab === "history",
  });

  const toggleMut = useMutation({
    mutationFn: (itemId: number) => toggleChecklistItem(checklistId, itemId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["checklist", checklistId] });
      qc.invalidateQueries({ queryKey: ["checklists"] });
      qc.invalidateQueries({ queryKey: ["audit-logs", "checklist", checklistId] });
    },
    onError: () => toast.error("Не удалось обновить пункт"),
  });

  const skipMut = useMutation({
    mutationFn: ({ itemId, note }: { itemId: number; note?: string }) =>
      skipChecklistItem(checklistId, itemId, note),
    onSuccess: (_data, variables) => {
      toast.success("Пункт пропущен");
      setSkipNote((prev) => {
        const next = { ...prev };
        delete next[variables.itemId];
        return next;
      });
      qc.invalidateQueries({ queryKey: ["checklist", checklistId] });
      qc.invalidateQueries({ queryKey: ["checklists"] });
      qc.invalidateQueries({ queryKey: ["audit-logs", "checklist", checklistId] });
    },
    onError: (err: Error) => toast.error(err.message ?? "Не удалось пропустить пункт"),
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

        {/* Deadline row */}
        {detail && <DeadlineDetailRow cl={detail} />}

        {/* Tabs */}
        <div className="shrink-0 flex border-b">
          <button
            type="button"
            onClick={() => setActiveTab("items")}
            className={cn(
              "flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors",
              activeTab === "items"
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            <ClipboardList className="size-3.5" />
            Пункты
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("history")}
            className={cn(
              "flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors",
              activeTab === "history"
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            <History className="size-3.5" />
            История
          </button>
        </div>

        {/* Progress bar (items tab only) */}
        {activeTab === "items" && detail && (
          <div className="shrink-0 border-b bg-muted/30 px-5 py-3">
            <ProgressBar total={detail.total_items} done={detail.completed_items} />
          </div>
        )}

        {/* Content */}
        <div className="flex-1 overflow-y-auto">
          {activeTab === "items" ? (
            isLoading ? (
              <div className="flex flex-1 items-center justify-center p-8">
                <div className="h-8 w-32 animate-pulse rounded-lg bg-muted" />
              </div>
            ) : detail?.items && detail.items.length > 0 ? (
              <div className="divide-y">
                {detail.items.map((item) => (
                  <div
                    key={item.id}
                    className={cn(
                      "px-5 py-3",
                      item.is_skipped && "opacity-50",
                    )}
                  >
                    <div className="flex items-start gap-3">
                      {/* Toggle button */}
                      <button
                        type="button"
                        disabled={
                          !isOpen ||
                          toggleMut.isPending ||
                          item.is_skipped
                        }
                        onClick={() => toggleMut.mutate(item.id)}
                        className={cn(
                          "mt-0.5 shrink-0 size-5 rounded border-2 transition-colors",
                          item.is_completed
                            ? "border-green-500 bg-green-500 text-white"
                            : "border-border hover:border-primary",
                          (!isOpen || item.is_skipped) && "cursor-not-allowed opacity-50",
                        )}
                      >
                        {item.is_completed && (
                          <svg viewBox="0 0 12 12" className="size-full p-0.5" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M2 6l3 3 5-5" />
                          </svg>
                        )}
                      </button>

                      <div className="flex-1 min-w-0">
                        <p
                          className={cn(
                            "text-sm font-medium",
                            (item.is_completed || item.is_skipped) && "text-muted-foreground line-through",
                          )}
                        >
                          {item.title}
                          {item.is_required && !item.is_completed && !item.is_skipped && (
                            <span className="ml-1.5 text-xs text-destructive">*</span>
                          )}
                          {item.is_skipped && (
                            <span className="ml-1.5 text-xs text-muted-foreground">(пропущен)</span>
                          )}
                        </p>
                        {item.is_completed && item.completed_by_name && (
                          <p className="mt-0.5 text-xs text-muted-foreground">{item.completed_by_name}</p>
                        )}
                        {item.note && !item.is_completed && (
                          <p className="mt-0.5 text-xs text-muted-foreground italic">{item.note}</p>
                        )}

                        {/* ── Photo thumbnails ───────────────────────── */}
                        {item.photos.length > 0 && (
                          <div className="mt-2 flex flex-wrap gap-1.5">
                            {item.photos.map((photo) => (
                              <SignedPhoto
                                key={photo.id}
                                rawUrl={photo.url}
                                alt={`Фото к пункту «${item.title}»`}
                                className="size-16 shrink-0"
                              />
                            ))}
                          </div>
                        )}
                        {/* ─────────────────────────────────────────────── */}
                      </div>

                      {/* Skip button for optional items */}
                      {isOpen && !item.is_required && !item.is_completed && !item.is_skipped && (
                        <button
                          type="button"
                          title="Пропустить пункт"
                          onClick={() => skipMut.mutate({ itemId: item.id, note: skipNote[item.id] })}
                          disabled={skipMut.isPending}
                          className="shrink-0 mt-0.5 text-muted-foreground hover:text-amber-600 dark:hover:text-amber-400 transition-colors"
                        >
                          <SkipForward className="size-4" />
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex flex-1 items-center justify-center p-8 text-center">
                <p className="text-sm text-muted-foreground">Нет пунктов в этом чек-листе</p>
              </div>
            )
          ) : (
            // History tab
            <div className="px-4">
              {logsLoading ? (
                <div className="flex items-center justify-center py-10">
                  <div className="h-6 w-32 animate-pulse rounded bg-muted" />
                </div>
              ) : (
                <AuditLogTimeline logs={auditLogs ?? []} />
              )}
            </div>
          )}
        </div>

        {/* Complete button */}
        {isOpen && isManager && allRequiredDone && activeTab === "items" && (
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

  const selectedTemplate = templates?.find((t) => t.id === form.template_id);

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
            {selectedTemplate?.deadline_offset_minutes != null && (
              <p className="text-xs text-muted-foreground flex items-center gap-1">
                <Clock className="size-3" />
                Дедлайн: {selectedTemplate.deadline_offset_minutes >= 60
                  ? `${Math.floor(selectedTemplate.deadline_offset_minutes / 60)} ч ${selectedTemplate.deadline_offset_minutes % 60 > 0 ? `${selectedTemplate.deadline_offset_minutes % 60} мин` : ""}`
                  : `${selectedTemplate.deadline_offset_minutes} мин`} после создания
              </p>
            )}
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
