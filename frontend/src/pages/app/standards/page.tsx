import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  listStandards,
  createStandard,
  updateStandard,
  STANDARD_CATEGORIES,
} from "@/api/standards.ts";
import type { Standard, StandardCreate } from "@/api/standards.ts";
import { BookOpen, Plus, Pencil, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils.ts";

function catLabel(val: string) {
  return STANDARD_CATEGORIES.find((c) => c.value === val)?.label ?? val;
}

// ── Create Modal ──────────────────────────────────────────────────────────

function CreateStandardModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [form, setForm] = useState<StandardCreate>({
    code: "",
    category: "service",
    title: "",
    description: "",
  });

  const mut = useMutation({
    mutationFn: (d: StandardCreate) => createStandard(d),
    onSuccess: () => {
      toast.success("Стандарт создан");
      qc.invalidateQueries({ queryKey: ["standards"] });
      onClose();
    },
    onError: (err: unknown) => {
      const detail =
        err && typeof err === "object" && "response" in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      toast.error(detail ?? "Не удалось создать стандарт");
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    mut.mutate({ ...form, description: form.description || undefined });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-md rounded-2xl border bg-card shadow-xl">
        <div className="flex items-center justify-between border-b px-5 py-4">
          <h2 className="text-lg font-semibold">Новый стандарт</h2>
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground text-xl">✕</button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4 p-5">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Код</label>
              <input
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm uppercase outline-none focus:ring-2 focus:ring-ring"
                value={form.code}
                onChange={(e) => setForm((f) => ({ ...f, code: e.target.value.toUpperCase() }))}
                placeholder="SRV-001"
                required
                autoFocus
              />
              <p className="text-xs text-muted-foreground">Уникальный идентификатор</p>
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Категория</label>
              <select
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
                value={form.category}
                onChange={(e) => setForm((f) => ({ ...f, category: e.target.value }))}
              >
                {STANDARD_CATEGORIES.map((c) => (
                  <option key={c.value} value={c.value}>{c.label}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Название</label>
            <input
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
              value={form.title}
              onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
              placeholder="Стандарт приветствия гостя"
              required
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Описание</label>
            <textarea
              className="w-full resize-none rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
              rows={3}
              value={form.description ?? ""}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              placeholder="Подробное описание стандарта"
            />
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

// ── Edit Modal ────────────────────────────────────────────────────────────

function EditStandardModal({ standard, onClose }: { standard: Standard; onClose: () => void }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    category: standard.category,
    title: standard.title,
    description: standard.description ?? "",
    is_active: standard.is_active,
  });

  const mut = useMutation({
    mutationFn: () =>
      updateStandard(standard.code, {
        category: form.category,
        title: form.title,
        description: form.description || undefined,
        is_active: form.is_active,
      }),
    onSuccess: () => {
      toast.success("Стандарт обновлён");
      qc.invalidateQueries({ queryKey: ["standards"] });
      onClose();
    },
    onError: () => toast.error("Не удалось обновить стандарт"),
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-md rounded-2xl border bg-card shadow-xl">
        <div className="flex items-center justify-between border-b px-5 py-4">
          <div>
            <h2 className="text-lg font-semibold">Изменить стандарт</h2>
            <p className="text-xs text-muted-foreground font-mono">{standard.code}</p>
          </div>
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground text-xl">✕</button>
        </div>
        <form
          onSubmit={(e) => { e.preventDefault(); mut.mutate(); }}
          className="space-y-4 p-5"
        >
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Категория</label>
            <select
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
              value={form.category}
              onChange={(e) => setForm((f) => ({ ...f, category: e.target.value }))}
            >
              {STANDARD_CATEGORIES.map((c) => (
                <option key={c.value} value={c.value}>{c.label}</option>
              ))}
            </select>
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Название</label>
            <input
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
              value={form.title}
              onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
              required
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Описание</label>
            <textarea
              className="w-full resize-none rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
              rows={3}
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
            />
          </div>
          <label className="flex cursor-pointer items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.checked }))}
              className="accent-primary"
            />
            Стандарт активен
          </label>
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

export default function StandardsPage() {
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [includeInactive, setIncludeInactive] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [editingStandard, setEditingStandard] = useState<Standard | null>(null);

  const { data: standards, isLoading } = useQuery({
    queryKey: ["standards", categoryFilter, includeInactive],
    queryFn: () =>
      listStandards({
        category: categoryFilter === "all" ? undefined : categoryFilter,
        include_inactive: includeInactive,
      }),
  });

  // Group by category
  const grouped = (standards ?? []).reduce<Record<string, Standard[]>>((acc, s) => {
    if (!acc[s.category]) acc[s.category] = [];
    acc[s.category].push(s);
    return acc;
  }, {});

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-4 md:p-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Стандарты</h1>
          <p className="text-sm text-muted-foreground">Корпоративные стандарты и нормы для чек-листов</p>
        </div>
        <button
          type="button"
          onClick={() => setCreateOpen(true)}
          className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90"
        >
          <Plus className="size-4" />Новый стандарт
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <select
          className="rounded-lg border bg-background px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-ring"
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
        >
          <option value="all">Все категории</option>
          {STANDARD_CATEGORIES.map((c) => (
            <option key={c.value} value={c.value}>{c.label}</option>
          ))}
        </select>
        <label className="flex cursor-pointer items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={includeInactive}
            onChange={(e) => setIncludeInactive(e.target.checked)}
            className="accent-primary"
          />
          Показывать неактивные
        </label>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-14 animate-pulse rounded-xl border bg-muted" />
          ))}
        </div>
      ) : !standards || standards.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed py-16 text-center">
          <BookOpen className="size-10 text-muted-foreground" />
          <p className="font-semibold">Нет стандартов</p>
          <p className="text-sm text-muted-foreground">Создайте первый корпоративный стандарт</p>
          <button
            type="button"
            onClick={() => setCreateOpen(true)}
            className="rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:opacity-90"
          >
            Создать стандарт
          </button>
        </div>
      ) : (
        <div className="space-y-6">
          {Object.entries(grouped).map(([cat, items]) => (
            <div key={cat}>
              <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                {catLabel(cat)} ({items.length})
              </h2>
              <div className="overflow-hidden rounded-xl border divide-y">
                {items.map((s) => (
                  <div
                    key={s.code}
                    className={cn(
                      "flex items-center gap-3 px-4 py-3",
                      !s.is_active && "opacity-50",
                    )}
                  >
                    <span className="w-24 shrink-0 font-mono text-xs font-semibold text-muted-foreground">
                      {s.code}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{s.title}</p>
                      {s.description && (
                        <p className="text-xs text-muted-foreground truncate">{s.description}</p>
                      )}
                    </div>
                    {!s.is_active && (
                      <span className="shrink-0 rounded-full border px-2 py-0.5 text-xs text-muted-foreground">Неактивен</span>
                    )}
                    <button
                      type="button"
                      onClick={() => setEditingStandard(s)}
                      className="shrink-0 rounded p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
                      title="Редактировать"
                    >
                      <Pencil className="size-4" />
                    </button>
                    <ChevronRight className="size-4 shrink-0 text-muted-foreground" />
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {createOpen && <CreateStandardModal onClose={() => setCreateOpen(false)} />}
      {editingStandard && (
        <EditStandardModal standard={editingStandard} onClose={() => setEditingStandard(null)} />
      )}
    </div>
  );
}
