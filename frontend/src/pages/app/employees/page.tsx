import { useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  listEmployees,
  createEmployee,
  updateEmployee,
  regenerateInviteCode,
  listRoles,
} from "@/api/employees.ts";
import type { Employee, EmployeeCreate, EmployeeUpdate } from "@/api/employees.ts";
import { listBranches } from "@/api/branches.ts";
import { Users, Plus, KeyRound, Copy, Pencil, Send } from "lucide-react";

const STATUS_LABEL: Record<string, string> = {
  active: "Активен",
  inactive: "Неактивен",
  fired: "Уволен",
};

const STATUS_COLOR: Record<string, string> = {
  active: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
  inactive: "bg-secondary text-secondary-foreground",
  fired: "bg-destructive/15 text-destructive",
};

const TELEGRAM_BOT_USERNAME = "mado_checklist_bot";

type FormValue = {
  full_name: string;
  phone: string;
  role_id: string;
  primary_branch_id: string;
  additional_branch_ids: string[];
  status: "active" | "inactive" | "fired";
};

function EmployeeDialog({
  open,
  onClose,
  initial,
  roles,
  branches,
  onSubmit,
  title,
  showStatus,
}: {
  open: boolean;
  onClose: () => void;
  initial: FormValue;
  roles: Array<{ id: number; name_ru: string }>;
  branches: Array<{ id: number; name: string }>;
  onSubmit: (value: FormValue) => Promise<void>;
  title: string;
  showStatus: boolean;
}) {
  const [value, setValue] = useState(initial);
  const [submitting, setSubmitting] = useState(false);

  if (!open) return null;

  const toggleBranch = (id: string) => {
    setValue((v) => ({
      ...v,
      additional_branch_ids: v.additional_branch_ids.includes(id)
        ? v.additional_branch_ids.filter((b) => b !== id)
        : [...v.additional_branch_ids, id],
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!value.role_id || !value.primary_branch_id) {
      toast.error("Выберите должность и филиал");
      return;
    }
    setSubmitting(true);
    try {
      await onSubmit(value);
      onClose();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-md max-h-[90vh] overflow-y-auto rounded-2xl border bg-card shadow-xl">
        <div className="flex items-center justify-between border-b px-5 py-4 sticky top-0 bg-card">
          <h2 className="text-lg font-semibold">{title}</h2>
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground text-xl">✕</button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4 p-5">
          <div className="space-y-1.5">
            <label className="text-sm font-medium">ФИО</label>
            <input
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
              value={value.full_name}
              onChange={(e) => setValue((v) => ({ ...v, full_name: e.target.value }))}
              placeholder="Алина Каримова"
              required
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Телефон</label>
            <input
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
              value={value.phone}
              onChange={(e) => setValue((v) => ({ ...v, phone: e.target.value }))}
              placeholder="+998 90 123 45 67"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Должность</label>
            <select
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
              value={value.role_id}
              onChange={(e) => setValue((v) => ({ ...v, role_id: e.target.value }))}
              required
            >
              <option value="">Выберите должность</option>
              {roles.map((r) => <option key={r.id} value={String(r.id)}>{r.name_ru}</option>)}
            </select>
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Основной филиал</label>
            <select
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
              value={value.primary_branch_id}
              onChange={(e) => setValue((v) => ({ ...v, primary_branch_id: e.target.value }))}
              required
            >
              <option value="">Выберите филиал</option>
              {branches.map((b) => <option key={b.id} value={String(b.id)}>{b.name}</option>)}
            </select>
          </div>
          {branches.length > 1 && (
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Дополнительные филиалы</label>
              <div className="flex flex-wrap gap-2">
                {branches.filter((b) => String(b.id) !== value.primary_branch_id).map((b) => {
                  const checked = value.additional_branch_ids.includes(String(b.id));
                  return (
                    <label key={b.id} className="flex cursor-pointer items-center gap-2 rounded-md border px-2.5 py-1.5 text-sm">
                      <input type="checkbox" checked={checked} onChange={() => toggleBranch(String(b.id))} className="accent-primary" />
                      {b.name}
                    </label>
                  );
                })}
              </div>
            </div>
          )}
          {showStatus && (
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Статус</label>
              <select
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
                value={value.status}
                onChange={(e) => setValue((v) => ({ ...v, status: e.target.value as FormValue["status"] }))}
              >
                <option value="active">Активен</option>
                <option value="inactive">Неактивен</option>
                <option value="fired">Уволен</option>
              </select>
            </div>
          )}
          <div className="flex gap-2 justify-end pt-2">
            <button type="button" onClick={onClose} className="rounded-lg border px-4 py-2 text-sm hover:bg-muted">Отмена</button>
            <button type="submit" disabled={submitting} className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90 disabled:opacity-50">
              {submitting ? "Сохраняем..." : "Сохранить"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function InviteDialog({
  employee,
  onClose,
}: {
  employee: Employee;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const regenMut = useMutation({
    mutationFn: () => regenerateInviteCode(employee.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["employees"] }),
  });
  const [code, setCode] = useState(employee.invite_code);
  const deepLink = `https://t.me/${TELEGRAM_BOT_USERNAME}?start=${code}`;

  const handleCopy = async (text: string, successMsg: string) => {
    try {
      await navigator.clipboard.writeText(text);
      toast.success(successMsg);
    } catch {
      toast.error("Не удалось скопировать");
    }
  };

  const handleRegen = async () => {
    try {
      const res = await regenMut.mutateAsync();
      setCode(res.invite_code);
      toast.success("Новый код сгенерирован");
    } catch {
      toast.error("Не удалось сгенерировать код");
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-sm rounded-2xl border bg-card shadow-xl">
        <div className="flex items-center justify-between border-b px-5 py-4">
          <h2 className="text-lg font-semibold">Вход через Telegram</h2>
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground text-xl">✕</button>
        </div>
        <div className="p-5 space-y-4">
          <p className="text-sm text-muted-foreground">
            Отправьте сотруднику <strong>{employee.full_name}</strong> ссылку или код — он откроет бота, нажмёт «Старт» и попадёт в свой чек-лист.
          </p>
          <div className="space-y-2">
            <label className="text-xs font-medium text-muted-foreground">Ссылка на бота</label>
            <div className="flex items-center gap-2 rounded-lg border bg-muted p-3">
              <span className="flex-1 truncate text-sm">{deepLink}</span>
              <button type="button" onClick={() => handleCopy(deepLink, "Ссылка скопирована")} className="text-muted-foreground hover:text-foreground p-1 rounded shrink-0">
                <Copy className="size-4" />
              </button>
            </div>
          </div>
          <div className="space-y-2">
            <label className="text-xs font-medium text-muted-foreground">Или код приглашения (после /start в боте)</label>
            <div className="flex items-center gap-2 rounded-lg border bg-muted p-4">
              <span className="flex-1 text-center text-2xl font-bold tracking-widest">{code}</span>
              <button type="button" onClick={() => handleCopy(code, "Код скопирован")} className="text-muted-foreground hover:text-foreground p-1 rounded">
                <Copy className="size-4" />
              </button>
            </div>
          </div>
          <button
            type="button"
            onClick={handleRegen}
            disabled={regenMut.isPending}
            className="w-full rounded-lg border px-4 py-2 text-sm hover:bg-muted disabled:opacity-50"
          >
            {regenMut.isPending ? "Генерируем..." : "Сгенерировать новый код"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function EmployeesPage() {
  const qc = useQueryClient();
  const { data: employees, isLoading: empLoading } = useQuery({ queryKey: ["employees"], queryFn: () => listEmployees() });
  const { data: roles, isLoading: rolesLoading } = useQuery({ queryKey: ["roles"], queryFn: listRoles });
  const { data: branches, isLoading: branchesLoading } = useQuery({ queryKey: ["branches"], queryFn: listBranches });

  const createMut = useMutation({
    mutationFn: (d: EmployeeCreate) => createEmployee(d),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["employees"] }),
  });
  const updateMut = useMutation({
    mutationFn: ({ id, d }: { id: number; d: EmployeeUpdate }) => updateEmployee(id, d),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["employees"] }),
  });

  const [createOpen, setCreateOpen] = useState(false);
  const [editingEmp, setEditingEmp] = useState<Employee | null>(null);
  const [inviteEmp, setInviteEmp] = useState<Employee | null>(null);

  const roleOptions = useMemo(() => (roles ?? []).map((r) => ({ id: r.id, name_ru: r.name_ru })), [roles]);
  const branchOptions = useMemo(() => (branches ?? []).map((b) => ({ id: b.id, name: b.name })), [branches]);

  const defaultForm: FormValue = {
    full_name: "",
    phone: "",
    role_id: String(roleOptions[0]?.id ?? ""),
    primary_branch_id: String(branchOptions[0]?.id ?? ""),
    additional_branch_ids: [],
    status: "active",
  };

  const handleCreate = async (v: FormValue) => {
    try {
      await createMut.mutateAsync({
        full_name: v.full_name,
        phone: v.phone || undefined,
        role_id: Number(v.role_id),
        primary_branch_id: Number(v.primary_branch_id),
        additional_branch_ids: v.additional_branch_ids.map(Number),
      });
      toast.success("Сотрудник добавлен");
    } catch {
      toast.error("Не удалось добавить сотрудника");
      throw new Error("create failed");
    }
  };

  const handleUpdate = async (v: FormValue) => {
    if (!editingEmp) return;
    try {
      await updateMut.mutateAsync({
        id: editingEmp.id,
        d: {
          full_name: v.full_name,
          phone: v.phone || undefined,
          role_id: Number(v.role_id),
          primary_branch_id: Number(v.primary_branch_id),
          additional_branch_ids: v.additional_branch_ids.map(Number),
          status: v.status,
        },
      });
      toast.success("Сотрудник обновлён");
    } catch {
      toast.error("Не удалось обновить сотрудника");
      throw new Error("update failed");
    }
  };

  const loading = empLoading || rolesLoading || branchesLoading;

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-4 md:p-8">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Сотрудники</h1>
          <p className="text-sm text-muted-foreground">Создавайте учётные записи и назначайте должности</p>
        </div>
        <button
          type="button"
          onClick={() => setCreateOpen(true)}
          disabled={roleOptions.length === 0 || branchOptions.length === 0}
          className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90 disabled:opacity-50"
        >
          <Plus className="size-4" />Сотрудник
        </button>
      </div>

      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-14 animate-pulse rounded-xl border bg-muted" />
          ))}
        </div>
      ) : !employees || employees.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed py-16 text-center">
          <Users className="size-10 text-muted-foreground" />
          <p className="font-semibold">Нет сотрудников</p>
          <p className="text-sm text-muted-foreground">Добавьте первого сотрудника, чтобы начать</p>
          <button type="button" onClick={() => setCreateOpen(true)} className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90">Добавить сотрудника</button>
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border">
          <table className="w-full text-sm">
            <thead className="bg-muted/50">
              <tr>
                <th className="px-4 py-3 text-left font-medium">ФИО</th>
                <th className="px-4 py-3 text-left font-medium">Должность</th>
                <th className="px-4 py-3 text-left font-medium">Филиал</th>
                <th className="px-4 py-3 text-left font-medium">Статус</th>
                <th className="px-4 py-3 text-left font-medium">Telegram</th>
                <th className="px-4 py-3 text-right font-medium">Действия</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {employees.map((emp) => (
                <tr key={emp.id} className="hover:bg-muted/30">
                  <td className="px-4 py-3 font-medium">{emp.full_name}</td>
                  <td className="px-4 py-3 text-muted-foreground">{emp.role_name}</td>
                  <td className="px-4 py-3 text-muted-foreground">{emp.primary_branch_name}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_COLOR[emp.status]}`}>
                      {STATUS_LABEL[emp.status]}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${emp.telegram_linked ? "bg-secondary text-secondary-foreground" : "border text-muted-foreground"}`}>
                      <Send className="size-3" />
                      {emp.telegram_linked ? "Привязан" : "Не привязан"}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex justify-end gap-1">
                      {!emp.telegram_linked && (
                        <button type="button" onClick={() => setInviteEmp(emp)} className="rounded p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground" title="Приглашение в Telegram">
                          <KeyRound className="size-4" />
                        </button>
                      )}
                      <button type="button" onClick={() => setEditingEmp(emp)} className="rounded p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground" title="Редактировать">
                        <Pencil className="size-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <EmployeeDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        initial={defaultForm}
        roles={roleOptions}
        branches={branchOptions}
        onSubmit={handleCreate}
        title="Новый сотрудник"
        showStatus={false}
      />

      {editingEmp && (
        <EmployeeDialog
          open
          onClose={() => setEditingEmp(null)}
          initial={{
            full_name: editingEmp.full_name,
            phone: editingEmp.phone ?? "",
            role_id: String(editingEmp.role_id),
            primary_branch_id: String(editingEmp.primary_branch_id),
            additional_branch_ids: editingEmp.additional_branch_ids.map(String),
            status: editingEmp.status,
          }}
          roles={roleOptions}
          branches={branchOptions}
          onSubmit={handleUpdate}
          title="Изменить сотрудника"
          showStatus
        />
      )}

      {inviteEmp && (
        <InviteDialog employee={inviteEmp} onClose={() => setInviteEmp(null)} />
      )}
    </div>
  );
}
