import { useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  listEmployees,
  createEmployee,
  updateEmployee,
  approveEmployee,
  rejectEmployee,
  deleteEmployee,
  regenerateInviteCode,
  unlinkEmployeeAccount,
  listRoles,
} from "@/api/employees.ts";
import type { Employee, EmployeeCreate, EmployeeUpdate, EmployeeStatus } from "@/api/employees.ts";
import { listBranches } from "@/api/branches.ts";
import { Users, Plus, KeyRound, Copy, Pencil, Send, Unlink, Search, Check, X, Phone, Trash2 } from "lucide-react";
import DeleteEmployeeDialog from "./delete-employee-dialog.tsx";

const STATUS_LABEL: Record<EmployeeStatus, string> = {
  pending: "🟡 На проверке",
  active: "🟢 Активен",
  blocked: "🔴 Заблокирован",
  archived: "⚪ Архив",
  inactive: "Неактивен",
  fired: "Уволен",
};

const STATUS_COLOR: Record<EmployeeStatus, string> = {
  pending: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400",
  active: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
  blocked: "bg-destructive/15 text-destructive",
  archived: "bg-secondary text-secondary-foreground",
  inactive: "bg-secondary text-secondary-foreground",
  fired: "bg-destructive/15 text-destructive",
};

const FILTERS: Array<{ id: "all" | EmployeeStatus; label: string }> = [
  { id: "all", label: "Все" },
  { id: "pending", label: "На проверке" },
  { id: "active", label: "Активные" },
  { id: "blocked", label: "Заблокированные" },
  { id: "archived", label: "Архив" },
];

const TELEGRAM_BOT_USERNAME = "mado_ibot";

type FormValue = {
  full_name: string;
  phone: string;
  role_id: string;
  primary_branch_id: string;
  additional_branch_ids: string[];
  status: EmployeeStatus;
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
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground text-xl cursor-pointer">✕</button>
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
            <label className="text-sm font-medium">Ресторан (основной филиал)</label>
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
                      <input type="checkbox" checked={checked} onChange={() => toggleBranch(String(b.id))} className="accent-primary cursor-pointer" />
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
                <option value="active">🟢 Активен</option>
                <option value="blocked">🔴 Заблокирован</option>
                <option value="archived">⚪ Архив</option>
              </select>
            </div>
          )}
          <div className="flex gap-2 justify-end pt-2">
            <button type="button" onClick={onClose} className="cursor-pointer rounded-lg border px-4 py-2 text-sm hover:bg-muted">Отмена</button>
            <button type="submit" disabled={submitting} className="cursor-pointer rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90 disabled:opacity-50">
              {submitting ? "Сохраняем..." : "Сохранить"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function ApproveDialog({
  employee,
  roles,
  branches,
  onClose,
  onSubmit,
}: {
  employee: Employee;
  roles: Array<{ id: number; name_ru: string }>;
  branches: Array<{ id: number; name: string }>;
  onClose: () => void;
  onSubmit: (roleId: number, branchId: number) => Promise<void>;
}) {
  const [roleId, setRoleId] = useState("");
  const [branchId, setBranchId] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!roleId || !branchId) {
      toast.error("Выберите ресторан и должность");
      return;
    }
    setSubmitting(true);
    try {
      await onSubmit(Number(roleId), Number(branchId));
      onClose();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-sm rounded-2xl border bg-card shadow-xl">
        <div className="flex items-center justify-between border-b px-5 py-4">
          <h2 className="text-lg font-semibold">Подтвердить сотрудника</h2>
          <button type="button" onClick={onClose} className="cursor-pointer text-muted-foreground hover:text-foreground text-xl">✕</button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4 p-5">
          <p className="text-sm text-muted-foreground">
            Назначьте ресторан и должность для <strong>{employee.full_name}</strong>, чтобы дать доступ к чек-листам.
          </p>
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Ресторан</label>
            <select
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
              value={branchId}
              onChange={(e) => setBranchId(e.target.value)}
              required
            >
              <option value="">Выберите ресторан</option>
              {branches.map((b) => <option key={b.id} value={String(b.id)}>{b.name}</option>)}
            </select>
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Должность</label>
            <select
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
              value={roleId}
              onChange={(e) => setRoleId(e.target.value)}
              required
            >
              <option value="">Выберите должность</option>
              {roles.map((r) => <option key={r.id} value={String(r.id)}>{r.name_ru}</option>)}
            </select>
          </div>
          <div className="flex gap-2 justify-end pt-2">
            <button type="button" onClick={onClose} className="cursor-pointer rounded-lg border px-4 py-2 text-sm hover:bg-muted">Отмена</button>
            <button type="submit" disabled={submitting} className="cursor-pointer rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90 disabled:opacity-50">
              {submitting ? "Сохраняем..." : "Подтвердить"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function RejectDialog({
  employee,
  onClose,
  onConfirm,
  submitting,
}: {
  employee: Employee;
  onClose: () => void;
  onConfirm: () => Promise<void>;
  submitting: boolean;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-sm rounded-2xl border bg-card shadow-xl">
        <div className="flex items-center justify-between border-b px-5 py-4">
          <h2 className="text-lg font-semibold">Отклонить заявку</h2>
          <button type="button" onClick={onClose} className="cursor-pointer text-muted-foreground hover:text-foreground text-xl">✕</button>
        </div>
        <div className="p-5 space-y-4">
          <p className="text-sm text-muted-foreground">
            Заявка сотрудника <strong>{employee.full_name}</strong> будет удалена. Он сможет отправить новую заявку через бота позже.
          </p>
          <div className="flex gap-2 justify-end">
            <button type="button" onClick={onClose} className="cursor-pointer rounded-lg border px-4 py-2 text-sm hover:bg-muted">Отмена</button>
            <button
              type="button"
              onClick={onConfirm}
              disabled={submitting}
              className="cursor-pointer rounded-lg bg-destructive px-4 py-2 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50"
            >
              {submitting ? "Отклоняем..." : "Отклонить"}
            </button>
          </div>
        </div>
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
  const [code, setCode] = useState(employee.invite_code ?? "");
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
          <button type="button" onClick={onClose} className="cursor-pointer text-muted-foreground hover:text-foreground text-xl">✕</button>
        </div>
        <div className="p-5 space-y-4">
          <p className="text-sm text-muted-foreground">
            Отправьте сотруднику <strong>{employee.full_name}</strong> ссылку или код — он откроет бота, нажмёт «Старт» и попадёт в свой чек-лист.
          </p>
          <div className="space-y-2">
            <label className="text-xs font-medium text-muted-foreground">Ссылка на бота</label>
            <div className="flex items-center gap-2 rounded-lg border bg-muted p-3">
              <span className="flex-1 truncate text-sm">{deepLink}</span>
              <button type="button" onClick={() => handleCopy(deepLink, "Ссылка скопирована")} className="cursor-pointer text-muted-foreground hover:text-foreground p-1 rounded shrink-0">
                <Copy className="size-4" />
              </button>
            </div>
          </div>
          <div className="space-y-2">
            <label className="text-xs font-medium text-muted-foreground">Или код приглашения (после /start в боте)</label>
            <div className="flex items-center gap-2 rounded-lg border bg-muted p-4">
              <span className="flex-1 text-center text-2xl font-bold tracking-widest">{code}</span>
              <button type="button" onClick={() => handleCopy(code, "Код скопирован")} className="cursor-pointer text-muted-foreground hover:text-foreground p-1 rounded">
                <Copy className="size-4" />
              </button>
            </div>
          </div>
          <button
            type="button"
            onClick={handleRegen}
            disabled={regenMut.isPending}
            className="cursor-pointer w-full rounded-lg border px-4 py-2 text-sm hover:bg-muted disabled:opacity-50"
          >
            {regenMut.isPending ? "Генерируем..." : "Сгенерировать новый код"}
          </button>
        </div>
      </div>
    </div>
  );
}

function UnlinkAccountDialog({
  employee,
  onClose,
  onConfirm,
  submitting,
}: {
  employee: Employee;
  onClose: () => void;
  onConfirm: () => Promise<void>;
  submitting: boolean;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-sm rounded-2xl border bg-card shadow-xl">
        <div className="flex items-center justify-between border-b px-5 py-4">
          <h2 className="text-lg font-semibold">Отвязать аккаунт</h2>
          <button type="button" onClick={onClose} className="cursor-pointer text-muted-foreground hover:text-foreground text-xl">✕</button>
        </div>
        <div className="p-5 space-y-4">
          <p className="text-sm text-muted-foreground">
            Учётная запись, привязанная к сотруднику <strong>{employee.full_name}</strong>, будет отвязана. Сотрудник
            сможет привязать новый аккаунт по коду приглашения. Текущий вход для старого аккаунта перестанет работать.
          </p>
          <div className="flex gap-2 justify-end">
            <button type="button" onClick={onClose} className="cursor-pointer rounded-lg border px-4 py-2 text-sm hover:bg-muted">
              Отмена
            </button>
            <button
              type="button"
              onClick={onConfirm}
              disabled={submitting}
              className="cursor-pointer rounded-lg bg-destructive px-4 py-2 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50"
            >
              {submitting ? "Отвязываем..." : "Отвязать"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function getErrorDetail(err: unknown): string | undefined {
  return err && typeof err === "object" && "response" in err
    ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
    : undefined;
}

export default function EmployeesPage() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | EmployeeStatus>("all");

  const { data: employees, isLoading: empLoading } = useQuery({
    queryKey: ["employees", search, statusFilter],
    queryFn: () =>
      listEmployees({
        q: search || undefined,
        status: statusFilter === "all" ? undefined : statusFilter,
      }),
  });
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
  const approveMut = useMutation({
    mutationFn: ({ id, roleId, branchId }: { id: number; roleId: number; branchId: number }) =>
      approveEmployee(id, { role_id: roleId, primary_branch_id: branchId, additional_branch_ids: [] }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["employees"] }),
  });
  const rejectMut = useMutation({
    mutationFn: (id: number) => rejectEmployee(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["employees"] }),
  });
  const deleteMut = useMutation({
    mutationFn: (id: number) => deleteEmployee(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["employees"] }),
  });
  const unlinkMut = useMutation({
    mutationFn: (id: number) => unlinkEmployeeAccount(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["employees"] }),
  });

  const [createOpen, setCreateOpen] = useState(false);
  const [editingEmp, setEditingEmp] = useState<Employee | null>(null);
  const [inviteEmp, setInviteEmp] = useState<Employee | null>(null);
  const [unlinkEmp, setUnlinkEmp] = useState<Employee | null>(null);
  const [approveEmp, setApproveEmp] = useState<Employee | null>(null);
  const [rejectEmp, setRejectEmp] = useState<Employee | null>(null);
  const [deleteEmp, setDeleteEmp] = useState<Employee | null>(null);

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

  const handleApprove = async (roleId: number, branchId: number) => {
    if (!approveEmp) return;
    try {
      await approveMut.mutateAsync({ id: approveEmp.id, roleId, branchId });
      toast.success("Сотрудник подтверждён");
    } catch {
      toast.error("Не удалось подтвердить сотрудника");
      throw new Error("approve failed");
    }
  };

  const handleReject = async () => {
    if (!rejectEmp) return;
    try {
      await rejectMut.mutateAsync(rejectEmp.id);
      toast.success("Заявка отклонена");
      setRejectEmp(null);
    } catch {
      toast.error("Не удалось отклонить заявку");
    }
  };

  const handleDelete = async () => {
    if (!deleteEmp) return;
    try {
      const res = await deleteMut.mutateAsync(deleteEmp.id);
      toast.success(
        res.mode === "deleted"
          ? "Сотрудник удалён"
          : "Сотрудник отвязан от Telegram и перенесён в архив (есть история)",
      );
      setDeleteEmp(null);
    } catch (err: unknown) {
      toast.error(getErrorDetail(err) ?? "Не удалось удалить сотрудника");
    }
  };

  const handleUnlink = async () => {
    if (!unlinkEmp) return;
    try {
      await unlinkMut.mutateAsync(unlinkEmp.id);
      toast.success("Аккаунт отвязан");
      setUnlinkEmp(null);
    } catch (err: unknown) {
      toast.error(getErrorDetail(err) ?? "Не удалось отвязать аккаунт. Возможно, у вас недостаточно прав.");
    }
  };

  const loading = empLoading || rolesLoading || branchesLoading;

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4 md:p-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Сотрудники</h1>
          <p className="text-sm text-muted-foreground">
            Все, кто писал боту, плюс сотрудники, добавленные вручную
          </p>
        </div>
        <button
          type="button"
          onClick={() => setCreateOpen(true)}
          disabled={roleOptions.length === 0 || branchOptions.length === 0}
          className="cursor-pointer flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90 disabled:opacity-50"
        >
          <Plus className="size-4" />Сотрудник
        </button>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative w-full sm:max-w-xs">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <input
            className="w-full rounded-lg border bg-background py-2 pl-9 pr-3 text-sm outline-none focus:ring-2 focus:ring-ring"
            placeholder="Поиск по имени, телефону, Telegram ID"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="flex flex-wrap gap-2">
          {FILTERS.map((f) => (
            <button
              key={f.id}
              type="button"
              onClick={() => setStatusFilter(f.id)}
              className={`cursor-pointer rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                statusFilter === f.id
                  ? "bg-primary text-primary-foreground"
                  : "border text-muted-foreground hover:bg-muted"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
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
          <p className="font-semibold">Никого не найдено</p>
          <p className="text-sm text-muted-foreground">
            Измените поиск/фильтр или добавьте сотрудника вручную
          </p>
          <button type="button" onClick={() => setCreateOpen(true)} className="cursor-pointer rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90">Добавить сотрудника</button>
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {employees.map((emp) => (
            <div key={emp.id} className="flex flex-col gap-3 rounded-xl border bg-card p-4">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="truncate font-semibold">{emp.full_name}</p>
                  <p className="truncate text-xs text-muted-foreground">
                    {emp.role_name ?? "Должность не назначена"}
                    {emp.primary_branch_name ? ` · ${emp.primary_branch_name}` : ""}
                  </p>
                </div>
                <span className={`shrink-0 inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_COLOR[emp.status]}`}>
                  {STATUS_LABEL[emp.status]}
                </span>
              </div>

              <div className="space-y-1 text-xs text-muted-foreground">
                {emp.phone && (
                  <div className="flex items-center gap-1.5">
                    <Phone className="size-3" />
                    <span>{emp.phone}</span>
                  </div>
                )}
                {emp.telegram_id && (
                  <div className="flex items-center gap-1.5">
                    <Send className="size-3" />
                    <span>
                      {emp.telegram_username ? `@${emp.telegram_username}` : "Telegram"} · ID {emp.telegram_id}
                    </span>
                  </div>
                )}
              </div>

              <div className="flex flex-wrap items-center gap-1.5 pt-1">
                <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${emp.has_claimed_account ? "bg-secondary text-secondary-foreground" : "border text-muted-foreground"}`}>
                  {emp.has_claimed_account ? "Веб-аккаунт привязан" : "Веб-аккаунт не привязан"}
                </span>
              </div>

              <div className="mt-auto flex flex-wrap justify-end gap-1.5 pt-2">
                {emp.status === "pending" ? (
                  <>
                    <button
                      type="button"
                      onClick={() => setRejectEmp(emp)}
                      className="cursor-pointer flex items-center gap-1 rounded-lg border px-2.5 py-1.5 text-xs font-medium text-destructive hover:bg-destructive/10"
                    >
                      <X className="size-3.5" />Отклонить
                    </button>
                    <button
                      type="button"
                      onClick={() => setApproveEmp(emp)}
                      className="cursor-pointer flex items-center gap-1 rounded-lg bg-primary px-2.5 py-1.5 text-xs font-medium text-primary-foreground hover:opacity-90"
                    >
                      <Check className="size-3.5" />Подтвердить
                    </button>
                  </>
                ) : (
                  <>
                    {!emp.telegram_linked && (
                      <button type="button" onClick={() => setInviteEmp(emp)} className="cursor-pointer rounded p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground" title="Приглашение в Telegram">
                        <KeyRound className="size-4" />
                      </button>
                    )}
                    {emp.has_claimed_account && (
                      <button
                        type="button"
                        onClick={() => setUnlinkEmp(emp)}
                        className="cursor-pointer rounded p-1.5 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                        title="Отвязать аккаунт"
                      >
                        <Unlink className="size-4" />
                      </button>
                    )}
                    <button type="button" onClick={() => setEditingEmp(emp)} className="cursor-pointer rounded p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground" title="Редактировать">
                      <Pencil className="size-4" />
                    </button>
                    <button
                      type="button"
                      onClick={() => setDeleteEmp(emp)}
                      className="cursor-pointer rounded p-1.5 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                      title="Удалить"
                    >
                      <Trash2 className="size-4" />
                    </button>
                  </>
                )}
              </div>
            </div>
          ))}
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
            role_id: String(editingEmp.role_id ?? ""),
            primary_branch_id: String(editingEmp.primary_branch_id ?? ""),
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

      {approveEmp && (
        <ApproveDialog
          employee={approveEmp}
          roles={roleOptions}
          branches={branchOptions}
          onClose={() => setApproveEmp(null)}
          onSubmit={handleApprove}
        />
      )}

      {rejectEmp && (
        <RejectDialog
          employee={rejectEmp}
          onClose={() => setRejectEmp(null)}
          onConfirm={handleReject}
          submitting={rejectMut.isPending}
        />
      )}

      {deleteEmp && (
        <DeleteEmployeeDialog
          employee={deleteEmp}
          onClose={() => setDeleteEmp(null)}
          onConfirm={handleDelete}
          submitting={deleteMut.isPending}
        />
      )}

      {inviteEmp && (
        <InviteDialog employee={inviteEmp} onClose={() => setInviteEmp(null)} />
      )}

      {unlinkEmp && (
        <UnlinkAccountDialog
          employee={unlinkEmp}
          onClose={() => setUnlinkEmp(null)}
          onConfirm={handleUnlink}
          submitting={unlinkMut.isPending}
        />
      )}
    </div>
  );
}
