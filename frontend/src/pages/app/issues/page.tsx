import { useState, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  listIssues,
  getIssue,
  createIssue,
  updateIssueStatus,
  addIssueComment,
  uploadIssuePhoto,
  photoSrc,
} from "@/api/issues.ts";
import type { Issue, IssueCreate } from "@/api/issues.ts";
import { listBranches } from "@/api/branches.ts";
import { getMyProfile } from "@/api/employees.ts";
import {
  AlertTriangle,
  Plus,
  ImagePlus,
  X,
  MessageSquare,
  Clock,
} from "lucide-react";
import { cn } from "@/lib/utils.ts";

// ── constants ─────────────────────────────────────────────────────────────────

const PRIORITIES = [
  { value: "low", label: "Низкий", color: "bg-secondary text-secondary-foreground" },
  { value: "medium", label: "Средний", color: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400" },
  { value: "high", label: "Высокий", color: "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400" },
  { value: "critical", label: "Критический", color: "bg-destructive/15 text-destructive" },
];

const STATUSES = [
  { value: "open", label: "Открыта", color: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400" },
  { value: "in_progress", label: "В работе", color: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400" },
  { value: "closed", label: "Закрыта", color: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400" },
];

const CATEGORIES = [
  { value: "general", label: "Общее" },
  { value: "equipment", label: "Оборудование" },
  { value: "hygiene", label: "Гигиена" },
  { value: "safety", label: "Безопасность" },
  { value: "supply", label: "Поставки" },
  { value: "staff", label: "Персонал" },
  { value: "client", label: "Клиент" },
];

const NEXT_STATUS: Record<string, string> = {
  open: "in_progress",
  in_progress: "closed",
};
const NEXT_LABEL: Record<string, string> = {
  open: "Взять в работу",
  in_progress: "Закрыть",
};

function priorityInfo(v: string) {
  return PRIORITIES.find((p) => p.value === v) ?? PRIORITIES[1];
}
function statusInfo(v: string) {
  return STATUSES.find((s) => s.value === v) ?? STATUSES[0];
}
function catLabel(v: string) {
  return CATEGORIES.find((c) => c.value === v)?.label ?? v;
}
function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString("ru-RU", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}

// ── photo picker ─────────────────────────────────────────────────────────────

function PhotoPicker({
  urls,
  onChange,
}: {
  urls: string[];
  onChange: (urls: string[]) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);

  const handleFiles = async (files: FileList | null) => {
    if (!files) return;
    setUploading(true);
    try {
      const results = await Promise.all(
        Array.from(files).map((f) => uploadIssuePhoto(f)),
      );
      onChange([...urls, ...results]);
    } catch {
      toast.error("Не удалось загрузить фото");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="space-y-2">
      <label className="text-sm font-medium">Фотографии</label>
      <div className="flex flex-wrap gap-2">
        {urls.map((url, i) => (
          <div key={i} className="relative size-20 shrink-0">
            <img src={photoSrc(url)} alt="" className="size-20 rounded-lg object-cover border" />
            <button
              type="button"
              onClick={() => onChange(urls.filter((_, j) => j !== i))}
              className="absolute -right-1.5 -top-1.5 flex size-5 items-center justify-center rounded-full bg-destructive text-white shadow"
            >
              <X className="size-3" />
            </button>
          </div>
        ))}
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          disabled={uploading}
          className="flex size-20 shrink-0 cursor-pointer flex-col items-center justify-center gap-1 rounded-lg border-2 border-dashed text-muted-foreground hover:border-primary hover:text-primary transition-colors disabled:opacity-50"
        >
          {uploading ? (
            <span className="text-xs">Загрузка...</span>
          ) : (
            <>
              <ImagePlus className="size-5" />
              <span className="text-xs">Добавить</span>
            </>
          )}
        </button>
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          multiple
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>
    </div>
  );
}

// ── create modal ─────────────────────────────────────────────────────────────

function CreateIssueModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const { data: branches } = useQuery({ queryKey: ["branches"], queryFn: listBranches });
  const { data: profile } = useQuery({ queryKey: ["my-profile"], queryFn: getMyProfile });

  const [form, setForm] = useState<IssueCreate>({
    title: "",
    description: "",
    branch_id: profile?.primary_branch_id ?? 0,
    category: "general",
    priority: "medium",
    photo_urls: [],
  });

  const mut = useMutation({
    mutationFn: (d: IssueCreate) => createIssue(d),
    onSuccess: () => {
      toast.success("Проблема зафиксирована");
      qc.invalidateQueries({ queryKey: ["issues"] });
      onClose();
    },
    onError: () => toast.error("Не удалось создать заявку"),
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.branch_id) { toast.error("Выберите филиал"); return; }
    mut.mutate({ ...form, description: form.description || undefined });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 sm:items-center sm:p-4">
      <div className="flex w-full max-h-[92vh] flex-col overflow-hidden rounded-t-2xl border bg-card shadow-xl sm:max-w-lg sm:rounded-2xl">
        <div className="flex shrink-0 items-center justify-between border-b px-5 py-4">
          <h2 className="text-lg font-semibold">Новая проблема</h2>
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground text-xl">✕</button>
        </div>
        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto space-y-4 p-5">
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Заголовок *</label>
            <input
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
              placeholder="Не работает кофе-машина"
              value={form.title}
              onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
              required
              autoFocus
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Описание</label>
            <textarea
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring resize-none"
              rows={3}
              placeholder="Подробно опишите проблему…"
              value={form.description ?? ""}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Категория</label>
              <select
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
                value={form.category}
                onChange={(e) => setForm((f) => ({ ...f, category: e.target.value }))}
              >
                {CATEGORIES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
              </select>
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Приоритет</label>
              <select
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
                value={form.priority}
                onChange={(e) => setForm((f) => ({ ...f, priority: e.target.value }))}
              >
                {PRIORITIES.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
              </select>
            </div>
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
              {branches?.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
            </select>
          </div>
          <PhotoPicker
            urls={form.photo_urls}
            onChange={(urls) => setForm((f) => ({ ...f, photo_urls: urls }))}
          />
          <div className="flex gap-2 justify-end pt-2 shrink-0">
            <button type="button" onClick={onClose} className="rounded-lg border px-4 py-2 text-sm hover:bg-muted">Отмена</button>
            <button
              type="submit"
              disabled={mut.isPending}
              className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90 disabled:opacity-50"
            >
              {mut.isPending ? "Отправка..." : "Отправить"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── issue detail modal ────────────────────────────────────────────────────────

function IssueDetailModal({
  issueId,
  isManager,
  onClose,
}: {
  issueId: number;
  isManager: boolean;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [comment, setComment] = useState("");
  const [lightbox, setLightbox] = useState<string | null>(null);

  const { data: detail, isLoading } = useQuery({
    queryKey: ["issue", issueId],
    queryFn: () => getIssue(issueId),
  });

  const statusMut = useMutation({
    mutationFn: (status: string) => updateIssueStatus(issueId, { status }),
    onSuccess: () => {
      toast.success("Статус обновлён");
      qc.invalidateQueries({ queryKey: ["issues"] });
      qc.invalidateQueries({ queryKey: ["issue", issueId] });
    },
    onError: () => toast.error("Не удалось обновить статус"),
  });

  const commentMut = useMutation({
    mutationFn: (text: string) => addIssueComment(issueId, text),
    onSuccess: () => {
      setComment("");
      qc.invalidateQueries({ queryKey: ["issue", issueId] });
    },
    onError: () => toast.error("Не удалось отправить комментарий"),
  });

  return (
    <>
      <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 sm:items-center sm:p-4">
        <div className="flex w-full max-h-[92vh] flex-col overflow-hidden rounded-t-2xl border bg-card shadow-xl sm:max-w-lg sm:rounded-2xl">
          <div className="flex shrink-0 items-center justify-between border-b px-5 py-4">
            <h2 className="text-lg font-semibold truncate pr-4">
              {detail ? detail.title : "Загрузка..."}
            </h2>
            <button type="button" onClick={onClose} className="shrink-0 text-muted-foreground hover:text-foreground text-xl">✕</button>
          </div>

          <div className="flex-1 overflow-y-auto">
            {isLoading ? (
              <div className="space-y-3 p-5">
                {Array.from({ length: 3 }).map((_, i) => (
                  <div key={i} className="h-8 animate-pulse rounded-lg bg-muted" />
                ))}
              </div>
            ) : detail ? (
              <>
                <div className="space-y-3 px-5 py-4 border-b">
                  <div className="flex flex-wrap gap-2">
                    {[
                      { label: statusInfo(detail.status).label, color: statusInfo(detail.status).color },
                      { label: priorityInfo(detail.priority).label, color: priorityInfo(detail.priority).color },
                    ].map((badge) => (
                      <span key={badge.label} className={cn("rounded-full px-2.5 py-0.5 text-xs font-medium", badge.color)}>
                        {badge.label}
                      </span>
                    ))}
                    <span className="rounded-full bg-muted px-2.5 py-0.5 text-xs font-medium">{catLabel(detail.category)}</span>
                  </div>
                  <p className="text-sm text-muted-foreground">{detail.branch_name}</p>
                  {detail.description && <p className="text-sm">{detail.description}</p>}
                  <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                    <span className="flex items-center gap-1"><Clock className="size-3" />Создано: {fmtDate(detail.created_at)}</span>
                    <span>Кем: {detail.reported_by_name}</span>
                    {detail.assigned_to_name && <span>Назначено: {detail.assigned_to_name}</span>}
                  </div>
                </div>

                {detail.photo_urls.length > 0 && (
                  <div className="px-5 py-4 border-b space-y-2">
                    <p className="text-sm font-medium">Фотографии ({detail.photo_urls.length})</p>
                    <div className="flex flex-wrap gap-2 overflow-hidden rounded-lg">
                      {detail.photo_urls.map((url, i) => (
                        <button
                          key={i}
                          type="button"
                          onClick={() => setLightbox(photoSrc(url))}
                          className="size-20 overflow-hidden rounded-lg border"
                        >
                          <img src={photoSrc(url)} alt="" className="size-20 object-cover transition-transform hover:scale-105" />
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                <div className="px-5 py-4 space-y-3">
                  <p className="text-sm font-medium flex items-center gap-1.5">
                    <MessageSquare className="size-4" />
                    Комментарии ({detail.comments.length})
                  </p>
                  {detail.comments.length === 0 ? (
                    <p className="text-sm text-muted-foreground">Пока нет комментариев</p>
                  ) : (
                    <div className="space-y-3">
                      {detail.comments.map((c) => (
                        <div key={c.id} className="rounded-lg bg-muted/50 px-3 py-2.5 space-y-1">
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-xs font-semibold">{c.author_name}</span>
                            <span className="text-xs text-muted-foreground">{fmtDate(c.created_at)}</span>
                          </div>
                          <p className="text-sm">{c.text}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </>
            ) : null}

            <div className="shrink-0 border-t px-5 py-4 space-y-3">
              <div className="flex gap-2">
                <input
                  className="flex-1 rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
                  placeholder="Написать комментарий…"
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey && comment.trim()) {
                      e.preventDefault();
                      commentMut.mutate(comment.trim());
                    }
                  }}
                />
                <button
                  type="button"
                  disabled={!comment.trim() || commentMut.isPending}
                  onClick={() => commentMut.mutate(comment.trim())}
                  className="rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
                >
                  Отпр.
                </button>
              </div>
              {isManager && detail && NEXT_STATUS[detail.status] && (
                <button
                  type="button"
                  onClick={() => statusMut.mutate(NEXT_STATUS[detail.status])}
                  disabled={statusMut.isPending}
                  className={cn(
                    "w-full rounded-lg px-4 py-2.5 text-sm font-semibold transition-colors disabled:opacity-50",
                    detail.status === "open"
                      ? "bg-yellow-500 text-white hover:bg-yellow-600"
                      : "bg-green-600 text-white hover:bg-green-700",
                  )}
                >
                  {statusMut.isPending ? "Обновляем..." : NEXT_LABEL[detail.status]}
                </button>
              )}
            </div>
          </div>
        </div>
      </div>

      {lightbox && (
        <div
          className="fixed inset-0 z-[60] flex items-center justify-center bg-black/90"
          onClick={() => setLightbox(null)}
        >
          <img src={lightbox} alt="" className="max-h-[90vh] max-w-[90vw] rounded-lg object-contain" />
        </div>
      )}
    </>
  );
}

// ── issue card ────────────────────────────────────────────────────────────────

function IssueCard({ issue, onClick }: { issue: Issue; onClick: () => void }) {
  const pi = priorityInfo(issue.priority);
  const si = statusInfo(issue.status);
  return (
    <button
      type="button"
      onClick={onClick}
      className="w-full cursor-pointer text-left space-y-3 rounded-xl border bg-card p-4 shadow-sm transition-all hover:border-primary/40 hover:shadow-md"
    >
      <div className="flex items-start gap-3">
        <div className="mt-0.5 flex shrink-0 size-8 items-center justify-center rounded-lg bg-muted">
          <AlertTriangle className={cn("size-4", issue.priority === "critical" ? "text-destructive" : "text-muted-foreground")} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-sm truncate">{issue.title}</p>
          <p className="text-xs text-muted-foreground truncate">{issue.branch_name}</p>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-1.5">
        <span className={cn("rounded-full px-2 py-0.5 text-xs font-medium", si.color)}>{si.label}</span>
        <span className={cn("rounded-full px-2 py-0.5 text-xs font-medium", pi.color)}>{pi.label}</span>
        <span className="ml-auto text-xs text-muted-foreground">{catLabel(issue.category)}</span>
      </div>
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>{issue.reported_by_name}</span>
        <div className="flex items-center gap-3">
          {issue.comment_count > 0 && (
            <span className="flex items-center gap-1"><MessageSquare className="size-3" />{issue.comment_count}</span>
          )}
          {issue.photo_urls.length > 0 && (
            <span className="flex items-center gap-1"><ImagePlus className="size-3" />{issue.photo_urls.length}</span>
          )}
          <span className="flex items-center gap-1"><Clock className="size-3" />{fmtDate(issue.created_at)}</span>
        </div>
      </div>
    </button>
  );
}

// ── page ───────────────────────────────────────────────────────────────────

export default function IssuesPage() {
  const [statusFilter, setStatusFilter] = useState<string>("open");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [createOpen, setCreateOpen] = useState(false);

  const { data: profile } = useQuery({ queryKey: ["my-profile"], queryFn: getMyProfile });
  const isManager = (profile?.role_level ?? 0) >= 1;

  const { data: issues, isLoading } = useQuery({
    queryKey: ["issues", statusFilter],
    queryFn: () => listIssues({ status: statusFilter || undefined }),
  });

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-4 md:p-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Проблемы</h1>
          <p className="text-sm text-muted-foreground">Фиксация и устранение инцидентов</p>
        </div>
        <button
          type="button"
          onClick={() => setCreateOpen(true)}
          className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90"
        >
          <Plus className="size-4" />Проблема
        </button>
      </div>

      <div className="flex gap-1 rounded-xl border bg-muted/30 p-1">
        {STATUSES.map((s) => (
          <button
            key={s.value}
            type="button"
            onClick={() => setStatusFilter(s.value)}
            className={cn(
              "flex-1 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
              statusFilter === s.value
                ? "bg-card shadow-sm text-foreground"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {s.label}
            {statusFilter === s.value && issues && (
              <span className="ml-1.5 rounded-full bg-primary/10 px-1.5 py-0.5 text-xs text-primary font-semibold">
                {issues.length}
              </span>
            )}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="grid gap-3 sm:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-32 animate-pulse rounded-xl border bg-muted" />
          ))}
        </div>
      ) : !issues || issues.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed py-16 text-center">
          <AlertTriangle className="size-10 text-muted-foreground" />
          <p className="font-semibold">
            {statusFilter === "open" ? "Открытых проблем нет" :
             statusFilter === "in_progress" ? "Нет проблем в работе" :
             "Нет закрытых проблем"}
          </p>
          {statusFilter === "open" && (
            <button
              type="button"
              onClick={() => setCreateOpen(true)}
              className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90"
            >
              Зафиксировать проблему
            </button>
          )}
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {issues.map((issue: Issue) => (
            <IssueCard key={issue.id} issue={issue} onClick={() => setSelectedId(issue.id)} />
          ))}
        </div>
      )}

      {selectedId !== null && (
        <IssueDetailModal
          issueId={selectedId}
          isManager={isManager}
          onClose={() => setSelectedId(null)}
        />
      )}
      {createOpen && <CreateIssueModal onClose={() => setCreateOpen(false)} />}
    </div>
  );
}
