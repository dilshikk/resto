import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  listTemplates,
  getTemplate,
  createTemplate,
  deactivateTemplate,
  addTemplateItem,
  removeTemplateItem,
} from "@/api/checklists.ts";
import type { ChecklistTemplate, TemplateCreate } from "@/api/checklists.ts";
import { listBranches } from "@/api/branches.ts";
import { ClipboardList, Plus, Trash2, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils.ts";

const CATEGORIES = [
  { value: "general", label: "Общий" },
  { value: "opening", label: "Открытие" },
  { value: "closing", label: "Закрытие" },
  { value: "cleaning", label: "Уборка" },
  { value: "kitchen", label: "Кухня" },
  { value: "bar", label: "Бар" },
  { value: "service", label: "Сервис" },
];

function catLabel(val: string) {
  return CATEGORIES.find((c) => c.value === val)?.label ?? val;
}

// ── Create Template Modal ─────────────────────────────────────────────────

function CreateTemplateModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (id: number) => void;
}) {
  const qc = useQueryClient();
  const { data: branches } = useQuery({ queryKey: ["branches"], queryFn: listBranches });
  const [form, setForm] = useState<TemplateCreate>({
    name: "",
    description: "",
    category: "general",
    branch_id: undefined,
  });

  const mut = useMutation({
    mutationFn: (data: TemplateCreate) => createTemplate(data),
    onSuccess: (t) => {
      toast.success("Шаблон создан");
      qc.invalidateQueries({ queryKey: ["templates"] });
      onCreated(t.id);
      onClose();
    },
    onError: () => toast.error("Не удалось создать шаблон"),
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    mut.mutate({ ...form, branch_id: form.branch_id || undefined, description: form.description || undefined });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-md rounded-2xl border bg-card shadow-xl">
        <div className="flex items-center justify-between border-b px-5 py-4">
          <h2 className="text-lg font-semibold">Новый шаблон</h2>
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground text-xl">✕</button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4 p-5">
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Название</label>
            <input
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              placeholder="Открытие ресторана"
              required
              autoFocus
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Описание</label>
            <textarea
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring resize-none"
              rows={2}
              value={form.description ?? ""}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              placeholder="Краткое описание шаблона"
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
                {CATEGORIES.map((c) => (
                  <option key={c.value} value={c.value}>{c.label}</option>
                ))}
              </select>
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Филиал</label>
              <select
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
                value={form.branch_id ? String(form.branch_id) : ""}
                onChange={(e) =>
                  setForm((f) => ({ ...f, branch_id: e.target.value ? Number(e.target.value) : undefined }))
                }
              >
                <option value="">Все</option>
                {branches?.map((b) => (
                  <option key={b.id} value={String(b.id)}>{b.name}</option>
                ))}
              </select>
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

// ── Add Item Modal ────────────────────────────────────────────────────────

function AddItemModal({ templateId, onClose }: { templateId: number; onClose: () => void }) {
  const qc = useQueryClient();
  const [title, setTitle] = useState("");
  const [isRequired, setIsRequired] = useState(true);

  const mut = useMutation({
    mutationFn: () => addTemplateItem(templateId, { title: title.trim(), is_required: isRequired }),
    onSuccess: () => {
      toast.success("Пункт добавлен");
      qc.invalidateQueries({ queryKey: ["template", templateId] });
      onClose();
    },
    onError: () => toast.error("Не удалось добавить пункт"),
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-sm rounded-2xl border bg-card shadow-xl">
        <div className="flex items-center justify-between border-b px-5 py-4">
          <h2 className="text-lg font-semibold">Добавить пункт</h2>
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground text-xl">✕</button>
        </div>
        <form
          onSubmit={(e) => { e.preventDefault(); mut.mutate(); }}
          className="space-y-4 p-5"
        >
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Задача</label>
            <input
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Проверить чистоту столов"
              required
              autoFocus
            />
          </div>
          <label className="flex cursor-pointer items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={isRequired}
              onChange={(e) => setIsRequired(e.target.checked)}
              className="accent-primary"
            />
            Обязательный пункт
          </label>
          <div className="flex gap-2 justify-end">
            <button type="button" onClick={onClose} className="rounded-lg border px-4 py-2 text-sm hover:bg-muted">Отмена</button>
            <button
              type="submit"
              disabled={mut.isPending || !title.trim()}
              className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90 disabled:opacity-50"
            >
              Добавить
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Template Detail Panel ─────────────────────────────────────────────────

function TemplateDetailPanel({
  templateId,
  onDeactivated,
}: {
  templateId: number;
  onDeactivated: () => void;
}) {
  const qc = useQueryClient();
  const [addItemOpen, setAddItemOpen] = useState(false);

  const { data: detail, isLoading } = useQuery({
    queryKey: ["template", templateId],
    queryFn: () => getTemplate(templateId),
  });

  const removeMut = useMutation({
    mutationFn: (itemId: number) => removeTemplateItem(templateId, itemId),
    onSuccess: () => {
      toast.success("Пункт удалён");
      qc.invalidateQueries({ queryKey: ["template", templateId] });
    },
    onError: () => toast.error("Не удалось удалить пункт"),
  });

  const deactivateMut = useMutation({
    mutationFn: () => deactivateTemplate(templateId),
    onSuccess: () => {
      toast.success("Шаблон деактивирован");
      qc.invalidateQueries({ queryKey: ["templates"] });
      onDeactivated();
    },
    onError: () => toast.error("Не удалось деактивировать"),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-12">
        <div className="h-8 w-40 animate-pulse rounded-lg bg-muted" />
      </div>
    );
  }

  if (!detail) return null;

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-2 min-w-0">
          <h2 className="text-xl font-bold truncate">{detail.name}</h2>
          {detail.description && (
            <p className="text-sm text-muted-foreground">{detail.description}</p>
          )}
          <div className="flex flex-wrap gap-2">
            <span className="inline-flex items-center rounded-full bg-secondary px-2.5 py-0.5 text-xs font-medium text-secondary-foreground">
              {catLabel(detail.category)}
            </span>
            {detail.branch_name && (
              <span className="inline-flex items-center rounded-full bg-secondary px-2.5 py-0.5 text-xs font-medium text-secondary-foreground">
                {detail.branch_name}
              </span>
            )}
          </div>
        </div>
        <button
          type="button"
          onClick={() => deactivateMut.mutate()}
          disabled={deactivateMut.isPending}
          className="shrink-0 rounded-lg border px-3 py-1.5 text-sm text-destructive hover:bg-muted disabled:opacity-50"
        >
          Деактивировать
        </button>
      </div>

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold">Пункты ({detail.items.length})</h3>
          <button
            type="button"
            onClick={() => setAddItemOpen(true)}
            className="flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:opacity-90"
          >
            <Plus className="size-3.5" />Добавить
          </button>
        </div>

        {detail.items.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed py-12 text-center">
            <p className="text-sm text-muted-foreground">
              Нет пунктов. Добавьте задачи для этого шаблона.
            </p>
            <button
              type="button"
              onClick={() => setAddItemOpen(true)}
              className="rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:opacity-90"
            >
              Добавить пункт
            </button>
          </div>
        ) : (
          <div className="overflow-hidden rounded-xl border divide-y">
            {detail.items.map((item, idx) => (
              <div key={item.id} className="flex items-center gap-3 px-4 py-3">
                <span className="w-6 shrink-0 text-right text-sm text-muted-foreground">{idx + 1}</span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{item.title}</p>
                  {!item.is_required && (
                    <span className="text-xs text-muted-foreground">Необязательный</span>
                  )}
                </div>
                <button
                  type="button"
                  onClick={() => removeMut.mutate(item.id)}
                  disabled={removeMut.isPending}
                  className="shrink-0 rounded p-1 text-muted-foreground hover:text-destructive disabled:opacity-50"
                >
                  <Trash2 className="size-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {addItemOpen && (
        <AddItemModal templateId={templateId} onClose={() => setAddItemOpen(false)} />
      )}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────

export default function TemplatesPage() {
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [createOpen, setCreateOpen] = useState(false);

  const { data: templates, isLoading } = useQuery({
    queryKey: ["templates"],
    queryFn: listTemplates,
  });

  return (
    <div className="flex h-full min-h-[calc(100vh-4rem)]">
      {/* Left panel */}
      <div
        className={cn(
          "border-r bg-card overflow-y-auto flex flex-col",
          selectedId
            ? "hidden md:flex md:w-72 md:shrink-0"
            : "flex-1 md:w-72 md:flex-none md:shrink-0",
        )}
      >
        <div className="flex items-center justify-between gap-3 border-b p-4 shrink-0">
          <h2 className="font-semibold">Шаблоны</h2>
          <button
            type="button"
            onClick={() => setCreateOpen(true)}
            className="flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:opacity-90"
          >
            <Plus className="size-3.5" />Новый
          </button>
        </div>

        <div className="flex-1 overflow-y-auto">
          {isLoading ? (
            <div className="space-y-2 p-3">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="h-16 animate-pulse rounded-lg bg-muted" />
              ))}
            </div>
          ) : !templates || templates.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-3 p-8 text-center">
              <ClipboardList className="size-10 text-muted-foreground" />
              <p className="text-sm font-semibold">Нет шаблонов</p>
              <p className="text-xs text-muted-foreground">Создайте первый шаблон чек-листа</p>
              <button
                type="button"
                onClick={() => setCreateOpen(true)}
                className="rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:opacity-90"
              >
                Создать шаблон
              </button>
            </div>
          ) : (
            <div className="p-2 space-y-1">
              {templates.map((tpl: ChecklistTemplate) => (
                <button
                  key={tpl.id}
                  type="button"
                  onClick={() => setSelectedId(tpl.id)}
                  className={cn(
                    "w-full cursor-pointer text-left rounded-lg px-3 py-3 transition-colors",
                    selectedId === tpl.id
                      ? "bg-primary text-primary-foreground"
                      : "hover:bg-muted",
                  )}
                >
                  <div className="flex items-center justify-between gap-2">
                    <p
                      className={cn(
                        "text-sm font-medium truncate",
                        selectedId === tpl.id ? "text-primary-foreground" : "",
                      )}
                    >
                      {tpl.name}
                    </p>
                    <ChevronRight
                      className={cn(
                        "size-4 shrink-0",
                        selectedId === tpl.id
                          ? "text-primary-foreground/70"
                          : "text-muted-foreground",
                      )}
                    />
                  </div>
                  <p
                    className={cn(
                      "mt-0.5 text-xs",
                      selectedId === tpl.id
                        ? "text-primary-foreground/70"
                        : "text-muted-foreground",
                    )}
                  >
                    {catLabel(tpl.category)} · {tpl.item_count} пунктов
                  </p>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Right panel */}
      <div
        className={cn(
          "flex-1 overflow-y-auto",
          !selectedId && "hidden md:flex md:items-center md:justify-center",
        )}
      >
        {selectedId ? (
          <>
            <div className="border-b px-4 py-3 md:hidden">
              <button
                type="button"
                onClick={() => setSelectedId(null)}
                className="text-sm font-medium text-primary"
              >
                ← Назад
              </button>
            </div>
            <TemplateDetailPanel
              templateId={selectedId}
              onDeactivated={() => setSelectedId(null)}
            />
          </>
        ) : (
          <div className="space-y-2 p-8 text-center">
            <ClipboardList className="mx-auto size-12 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">Выберите шаблон для просмотра</p>
          </div>
        )}
      </div>

      {createOpen && (
        <CreateTemplateModal
          onClose={() => setCreateOpen(false)}
          onCreated={(id) => setSelectedId(id)}
        />
      )}
    </div>
  );
}
