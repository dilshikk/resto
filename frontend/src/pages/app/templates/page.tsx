import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  listTemplates,
  getTemplate,
  createTemplate,
  updateTemplate,
  deactivateTemplate,
  addTemplateItem,
  removeTemplateItem,
} from "@/api/checklists.ts";
import type { ChecklistTemplate, TemplateCreate, TaskType } from "@/api/checklists.ts";
import { listBranches } from "@/api/branches.ts";
import { listStandards } from "@/api/standards.ts";
import { listRoles } from "@/api/employees.ts";
import { ClipboardList, Plus, Trash2, ChevronRight, Camera, MessageSquare, Users } from "lucide-react";
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

const TASK_TYPES: { value: TaskType; label: string; hint: string }[] = [
  { value: "checkbox", label: "Галочка", hint: "Просто отметить выполненным" },
  { value: "number", label: "Число", hint: "Сотрудник вводит число" },
  { value: "temperature", label: "Температура", hint: "Сотрудник вводит температуру" },
  { value: "photo", label: "Фото", hint: "Сотрудник прикладывает фото как ответ" },
  { value: "yes_no", label: "Да / Нет", hint: "Сотрудник выбирает да или нет" },
  { value: "text", label: "Текст", hint: "Сотрудник вводит текстовый ответ" },
];

function catLabel(val: string) {
  return CATEGORIES.find((c) => c.value === val)?.label ?? val;
}

// ── Role multi-select (shared by create + edit) ────────────────────────────

function RoleMultiSelect({
  selected,
  onChange,
}: {
  selected: number[];
  onChange: (ids: number[]) => void;
}) {
  const { data: roles } = useQuery({ queryKey: ["roles"], queryFn: listRoles });

  const toggle = (roleId: number) => {
    onChange(selected.includes(roleId) ? selected.filter((id) => id !== roleId) : [...selected, roleId]);
  };

  return (
    <div className="space-y-1.5">
      <label className="text-sm font-medium flex items-center gap-1.5">
        <Users className="size-3.5 text-muted-foreground" />
        Должности
      </label>
      <p className="text-xs text-muted-foreground">
        Кто увидит этот чек-лист. Если ничего не выбрано — увидят все должности.
      </p>
      <div className="flex flex-wrap gap-1.5">
        {roles?.map((role) => {
          const active = selected.includes(role.id);
          return (
            <button
              key={role.id}
              type="button"
              onClick={() => toggle(role.id)}
              className={cn(
                "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
                active
                  ? "border-primary bg-primary text-primary-foreground"
                  : "hover:bg-muted",
              )}
            >
              {role.name_ru}
            </button>
          );
        })}
        {!roles?.length && (
          <p className="text-xs text-muted-foreground">Нет настроенных должностей</p>
        )}
      </div>
    </div>
  );
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
    role_ids: [],
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
      <div className="w-full max-w-md rounded-2xl border bg-card shadow-xl max-h-[90vh] overflow-y-auto">
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

          <RoleMultiSelect
            selected={form.role_ids ?? []}
            onChange={(role_ids) => setForm((f) => ({ ...f, role_ids }))}
          />

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
  const { data: standards } = useQuery({
    queryKey: ["standards", "all", false],
    queryFn: () => listStandards(),
  });

  const [title, setTitle] = useState("");
  const [isRequired, setIsRequired] = useState(true);
  const [requiresPhoto, setRequiresPhoto] = useState(false);
  const [requiresComment, setRequiresComment] = useState(false);
  const [standardCode, setStandardCode] = useState("");
  const [taskType, setTaskType] = useState<TaskType>("checkbox");

  const mut = useMutation({
    mutationFn: () =>
      addTemplateItem(templateId, {
        title: title.trim(),
        is_required: isRequired,
        requires_photo: requiresPhoto,
        requires_comment: requiresComment,
        standard_code: standardCode || undefined,
        task_type: taskType,
      }),
    onSuccess: () => {
      toast.success("Пункт добавлен");
      qc.invalidateQueries({ queryKey: ["template", templateId] });
      onClose();
    },
    onError: () => toast.error("Не удалось добавить пункт"),
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-sm rounded-2xl border bg-card shadow-xl max-h-[90vh] overflow-y-auto">
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

          {/* Task type */}
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Тип задачи</label>
            <select
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
              value={taskType}
              onChange={(e) => setTaskType(e.target.value as TaskType)}
            >
              {TASK_TYPES.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
            <p className="text-xs text-muted-foreground">
              {TASK_TYPES.find((t) => t.value === taskType)?.hint}
            </p>
          </div>

          {/* Standard code */}
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Стандарт <span className="text-muted-foreground font-normal">(необязательно)</span></label>
            <select
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
              value={standardCode}
              onChange={(e) => setStandardCode(e.target.value)}
            >
              <option value="">Без привязки к стандарту</option>
              {standards?.map((s) => (
                <option key={s.code} value={s.code}>{s.code} — {s.title}</option>
              ))}
            </select>
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

          {/* Confirmation & photo report section */}
          <div className="rounded-lg border bg-muted/30 p-3 space-y-2.5">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
              Подтверждение и фотоотчёт
            </p>

            <label className="flex cursor-pointer items-start gap-2.5 text-sm">
              <input
                type="checkbox"
                checked={requiresPhoto}
                onChange={(e) => setRequiresPhoto(e.target.checked)}
                className="mt-0.5 accent-primary"
              />
              <span className="flex flex-col gap-0.5">
                <span className="font-medium flex items-center gap-1.5">
                  <Camera className="size-3.5 text-muted-foreground" />
                  Требовать фотоотчёт
                </span>
                <span className="text-xs text-muted-foreground">
                  Сотрудник должен прикрепить фото перед отметкой выполнения
                </span>
              </span>
            </label>

            <label className="flex cursor-pointer items-start gap-2.5 text-sm">
              <input
                type="checkbox"
                checked={requiresComment}
                onChange={(e) => setRequiresComment(e.target.checked)}
                className="mt-0.5 accent-primary"
              />
              <span className="flex flex-col gap-0.5">
                <span className="font-medium flex items-center gap-1.5">
                  <MessageSquare className="size-3.5 text-muted-foreground" />
                  Требовать комментарий
                </span>
                <span className="text-xs text-muted-foreground">
                  Сотрудник должен добавить текстовое описание результата
                </span>
              </span>
            </label>
          </div>

          <div className="flex gap-2 justify-end">
            <button type="button" onClick={onClose} className="rounded-lg border px-4 py-2 text-sm hover:bg-muted">Отмена</button>
            <button
              type="submit"
              disabled={mut.isPending || !title.trim()}
              className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90 disabled:opacity-50"
            >
              {mut.isPending ? "Добавляем..." : "Добавить"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Edit Roles Modal ────────────────────────────────────────────────────────

function EditRolesModal({
  template,
  onClose,
}: {
  template: ChecklistTemplate;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [roleIds, setRoleIds] = useState<number[]>(template.role_ids ?? []);

  const mut = useMutation({
    mutationFn: () =>
      updateTemplate(template.id, {
        name: template.name,
        description: template.description,
        category: template.category,
        branch_id: template.branch_id,
        deadline_offset_minutes: template.deadline_offset_minutes,
        role_ids: roleIds,
      }),
    onSuccess: () => {
      toast.success("Должности обновлены");
      qc.invalidateQueries({ queryKey: ["templates"] });
      qc.invalidateQueries({ queryKey: ["template", template.id] });
      onClose();
    },
    onError: () => toast.error("Не удалось обновить должности"),
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-sm rounded-2xl border bg-card shadow-xl">
        <div className="flex items-center justify-between border-b px-5 py-4">
          <h2 className="text-lg font-semibold">Должности</h2>
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground text-xl">✕</button>
        </div>
        <div className="space-y-4 p-5">
          <RoleMultiSelect selected={roleIds} onChange={setRoleIds} />
          <div className="flex gap-2 justify-end pt-2">
            <button type="button" onClick={onClose} className="rounded-lg border px-4 py-2 text-sm hover:bg-muted">Отмена</button>
            <button
              type="button"
              onClick={() => mut.mutate()}
              disabled={mut.isPending}
              className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90 disabled:opacity-50"
            >
              {mut.isPending ? "Сохраняем..." : "Сохранить"}
            </button>
          </div>
        </div>
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
  const [editRolesOpen, setEditRolesOpen] = useState(false);

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
            <button
              type="button"
              onClick={() => setEditRolesOpen(true)}
              className="inline-flex items-center gap-1 rounded-full border border-dashed px-2.5 py-0.5 text-xs font-medium text-muted-foreground hover:border-primary hover:text-primary"
            >
              <Users className="size-3" />
              {detail.role_names?.length ? detail.role_names.join(", ") : "Все должности"}
            </button>
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
                  <div className="flex flex-wrap items-center gap-2 mt-0.5">
                    <span className="text-xs text-muted-foreground">
                      {TASK_TYPES.find((t) => t.value === item.task_type)?.label ?? "Галочка"}
                    </span>
                    {!item.is_required && (
                      <span className="text-xs text-muted-foreground">Необязательный</span>
                    )}
                    {item.standard_code && (
                      <span className="font-mono text-xs text-primary/70">{item.standard_code}</span>
                    )}
                    {item.requires_photo && (
                      <span className="inline-flex items-center gap-0.5 text-xs text-blue-600 dark:text-blue-400">
                        <Camera className="size-3" />
                        Фото
                      </span>
                    )}
                    {item.requires_comment && (
                      <span className="inline-flex items-center gap-0.5 text-xs text-amber-600 dark:text-amber-400">
                        <MessageSquare className="size-3" />
                        Комментарий
                      </span>
                    )}
                  </div>
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
      {editRolesOpen && (
        <EditRolesModal template={detail} onClose={() => setEditRolesOpen(false)} />
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
                    {tpl.role_names?.length ? ` · ${tpl.role_names.join(", ")}` : ""}
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
