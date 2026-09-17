import { useMemo, useState } from "react";
import { useMutation, useQuery } from "convex/react";
import { ConvexError } from "convex/values";
import { toast } from "sonner";
import { api } from "@/convex/_generated/api.js";
import type { Id } from "@/convex/_generated/dataModel.d.ts";
import { Button } from "@/components/ui/button.tsx";
import { Input } from "@/components/ui/input.tsx";
import { Label } from "@/components/ui/label.tsx";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select.tsx";
import { Checkbox } from "@/components/ui/checkbox.tsx";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog.tsx";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table.tsx";
import { Badge } from "@/components/ui/badge.tsx";
import { Skeleton } from "@/components/ui/skeleton.tsx";
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty.tsx";
import { Users, Plus, KeyRound, Copy, Pencil } from "lucide-react";

function errorMessage(err: unknown, fallback: string) {
  if (err instanceof ConvexError) {
    const data = err.data as { message?: string };
    return data.message ?? fallback;
  }
  return fallback;
}

const STATUS_LABEL: Record<string, string> = {
  active: "Активен",
  inactive: "Неактивен",
  fired: "Уволен",
};

const STATUS_VARIANT: Record<string, "default" | "secondary" | "destructive"> = {
  active: "default",
  inactive: "secondary",
  fired: "destructive",
};

type EmployeeFormValue = {
  fullName: string;
  phone: string;
  roleId: string;
  primaryBranchId: string;
  additionalBranchIds: string[];
  status: "active" | "inactive" | "fired";
};

function branchOptionLabel(name: string) {
  return name;
}

function EmployeeFormDialog({
  open,
  onOpenChange,
  initial,
  roles,
  branches,
  onSubmit,
  title,
  showStatus,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initial: EmployeeFormValue;
  roles: Array<{ _id: Id<"roles">; nameRu: string }>;
  branches: Array<{ _id: Id<"branches">; name: string }>;
  onSubmit: (value: EmployeeFormValue) => Promise<void>;
  title: string;
  showStatus: boolean;
}) {
  const [value, setValue] = useState(initial);
  const [submitting, setSubmitting] = useState(false);

  const toggleAdditionalBranch = (branchId: string) => {
    setValue((v) => ({
      ...v,
      additionalBranchIds: v.additionalBranchIds.includes(branchId)
        ? v.additionalBranchIds.filter((id) => id !== branchId)
        : [...v.additionalBranchIds, branchId],
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!value.roleId || !value.primaryBranchId) {
      toast.error("Выберите должность и филиал");
      return;
    }
    setSubmitting(true);
    try {
      await onSubmit(value);
      onOpenChange(false);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (next) setValue(initial);
        onOpenChange(next);
      }}
    >
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="emp-name">ФИО</Label>
            <Input
              id="emp-name"
              value={value.fullName}
              onChange={(e) => setValue((v) => ({ ...v, fullName: e.target.value }))}
              placeholder="Алина Каримова"
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="emp-phone">Телефон</Label>
            <Input
              id="emp-phone"
              value={value.phone}
              onChange={(e) => setValue((v) => ({ ...v, phone: e.target.value }))}
              placeholder="+998 90 123 45 67"
            />
          </div>
          <div className="space-y-2">
            <Label>Должность</Label>
            <Select
              value={value.roleId}
              onValueChange={(roleId) => setValue((v) => ({ ...v, roleId }))}
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Выберите должность" />
              </SelectTrigger>
              <SelectContent>
                {roles.map((role) => (
                  <SelectItem key={role._id} value={role._id}>
                    {role.nameRu}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>Основной филиал</Label>
            <Select
              value={value.primaryBranchId}
              onValueChange={(primaryBranchId) =>
                setValue((v) => ({ ...v, primaryBranchId }))
              }
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Выберите филиал" />
              </SelectTrigger>
              <SelectContent>
                {branches.map((branch) => (
                  <SelectItem key={branch._id} value={branch._id}>
                    {branchOptionLabel(branch.name)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {branches.length > 1 && (
            <div className="space-y-2">
              <Label>Дополнительные филиалы</Label>
              <div className="flex flex-wrap gap-2">
                {branches
                  .filter((b) => b._id !== value.primaryBranchId)
                  .map((branch) => {
                    const checked = value.additionalBranchIds.includes(branch._id);
                    return (
                      <label
                        key={branch._id}
                        className="flex cursor-pointer items-center gap-2 rounded-md border px-2.5 py-1.5 text-sm"
                      >
                        <Checkbox
                          checked={checked}
                          onCheckedChange={() => toggleAdditionalBranch(branch._id)}
                        />
                        {branch.name}
                      </label>
                    );
                  })}
              </div>
            </div>
          )}
          {showStatus && (
            <div className="space-y-2">
              <Label>Статус</Label>
              <Select
                value={value.status}
                onValueChange={(status) =>
                  setValue((v) => ({ ...v, status: status as EmployeeFormValue["status"] }))
                }
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="active">Активен</SelectItem>
                  <SelectItem value="inactive">Неактивен</SelectItem>
                  <SelectItem value="fired">Уволен</SelectItem>
                </SelectContent>
              </Select>
            </div>
          )}
          <DialogFooter>
            <Button type="submit" disabled={submitting}>
              {submitting ? "Сохраняем..." : "Сохранить"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function InviteCodeDialog({
  employeeId,
  fullName,
  code,
  open,
  onOpenChange,
}: {
  employeeId: Id<"employees">;
  fullName: string;
  code: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const regenerate = useMutation(api.employees.regenerateInviteCode);
  const [currentCode, setCurrentCode] = useState(code);
  const [regenerating, setRegenerating] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(currentCode);
      toast.success("Код скопирован");
    } catch {
      toast.error("Не удалось скопировать код");
    }
  };

  const handleRegenerate = async () => {
    setRegenerating(true);
    try {
      const newCode = await regenerate({ employeeId });
      setCurrentCode(newCode);
      toast.success("Новый код сгенерирован");
    } catch (err) {
      toast.error(errorMessage(err, "Не удалось сгенерировать код"));
    } finally {
      setRegenerating(false);
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setCurrentCode(code);
        onOpenChange(next);
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Код приглашения для {fullName}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Передайте этот код сотруднику. При первом входе в систему он введёт его,
            чтобы привязать свою учётную запись.
          </p>
          <div className="flex items-center gap-2 rounded-lg border bg-muted p-4">
            <span className="flex-1 text-center text-2xl font-bold tracking-widest">
              {currentCode}
            </span>
            <Button variant="ghost" size="icon" onClick={handleCopy} aria-label="Скопировать">
              <Copy className="size-4" />
            </Button>
          </div>
          <Button
            variant="secondary"
            className="w-full"
            onClick={handleRegenerate}
            disabled={regenerating}
          >
            {regenerating ? "Генерируем..." : "Сгенерировать новый код"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default function EmployeesPage() {
  const employees = useQuery(api.employees.listEmployees, {});
  const roles = useQuery(api.roles.listRoles, {});
  const branches = useQuery(api.branches.listBranches, {});
  const createEmployee = useMutation(api.employees.createEmployee);
  const updateEmployee = useMutation(api.employees.updateEmployee);

  const [createOpen, setCreateOpen] = useState(false);
  const [editingId, setEditingId] = useState<Id<"employees"> | null>(null);
  const [inviteFor, setInviteFor] = useState<Id<"employees"> | null>(null);

  const editingEmployee = employees?.find((e) => e._id === editingId);
  const inviteEmployee = employees?.find((e) => e._id === inviteFor);

  const roleOptions = useMemo(
    () => (roles ?? []).map((r) => ({ _id: r._id, nameRu: r.nameRu })),
    [roles],
  );
  const branchOptions = useMemo(
    () => (branches ?? []).map((b) => ({ _id: b._id, name: b.name })),
    [branches],
  );

  const defaultForm: EmployeeFormValue = {
    fullName: "",
    phone: "",
    roleId: roleOptions[0]?._id ?? "",
    primaryBranchId: branchOptions[0]?._id ?? "",
    additionalBranchIds: [],
    status: "active",
  };

  const handleCreate = async (value: EmployeeFormValue) => {
    try {
      await createEmployee({
        fullName: value.fullName,
        phone: value.phone || undefined,
        roleId: value.roleId as Id<"roles">,
        primaryBranchId: value.primaryBranchId as Id<"branches">,
        additionalBranchIds: value.additionalBranchIds as Array<Id<"branches">>,
      });
      toast.success("Сотрудник добавлен");
    } catch (err) {
      toast.error(errorMessage(err, "Не удалось добавить сотрудника"));
      throw err;
    }
  };

  const handleUpdate = async (value: EmployeeFormValue) => {
    if (!editingId) return;
    try {
      await updateEmployee({
        employeeId: editingId,
        fullName: value.fullName,
        phone: value.phone || undefined,
        roleId: value.roleId as Id<"roles">,
        primaryBranchId: value.primaryBranchId as Id<"branches">,
        additionalBranchIds: value.additionalBranchIds as Array<Id<"branches">>,
        status: value.status,
      });
      toast.success("Сотрудник обновлён");
    } catch (err) {
      toast.error(errorMessage(err, "Не удалось обновить сотрудника"));
      throw err;
    }
  };

  const loading = employees === undefined || roles === undefined || branches === undefined;

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-4 md:p-8">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Сотрудники</h1>
          <p className="text-sm text-muted-foreground">
            Создавайте учётные записи и назначайте должности
          </p>
        </div>
        <Button
          onClick={() => setCreateOpen(true)}
          className="gap-2"
          disabled={roleOptions.length === 0 || branchOptions.length === 0}
        >
          <Plus className="size-4" />
          Сотрудник
        </Button>
      </div>

      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-14 w-full" />
          ))}
        </div>
      ) : employees.length === 0 ? (
        <Empty>
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <Users />
            </EmptyMedia>
            <EmptyTitle>Нет сотрудников</EmptyTitle>
            <EmptyDescription>Добавьте первого сотрудника, чтобы начать</EmptyDescription>
          </EmptyHeader>
          <EmptyContent>
            <Button size="sm" onClick={() => setCreateOpen(true)}>
              Добавить сотрудника
            </Button>
          </EmptyContent>
        </Empty>
      ) : (
        <div className="overflow-hidden rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>ФИО</TableHead>
                <TableHead>Должность</TableHead>
                <TableHead>Филиал</TableHead>
                <TableHead>Статус</TableHead>
                <TableHead>Аккаунт</TableHead>
                <TableHead className="text-right">Действия</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {employees.map((emp) => (
                <TableRow key={emp._id}>
                  <TableCell className="font-medium">{emp.fullName}</TableCell>
                  <TableCell>{emp.roleName}</TableCell>
                  <TableCell>{emp.primaryBranchName}</TableCell>
                  <TableCell>
                    <Badge variant={STATUS_VARIANT[emp.status]}>
                      {STATUS_LABEL[emp.status]}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    {emp.hasClaimedAccount ? (
                      <Badge variant="secondary">Привязан</Badge>
                    ) : (
                      <Badge variant="outline">Не привязан</Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-1">
                      {!emp.hasClaimedAccount && (
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          onClick={() => setInviteFor(emp._id)}
                          aria-label="Код приглашения"
                        >
                          <KeyRound className="size-4" />
                        </Button>
                      )}
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        onClick={() => setEditingId(emp._id)}
                        aria-label="Редактировать"
                      >
                        <Pencil className="size-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <EmployeeFormDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        initial={defaultForm}
        roles={roleOptions}
        branches={branchOptions}
        onSubmit={handleCreate}
        title="Новый сотрудник"
        showStatus={false}
      />

      {editingEmployee && (
        <EmployeeFormDialog
          open={editingId !== null}
          onOpenChange={(open) => !open && setEditingId(null)}
          initial={{
            fullName: editingEmployee.fullName,
            phone: editingEmployee.phone ?? "",
            roleId: editingEmployee.roleId,
            primaryBranchId: editingEmployee.primaryBranchId,
            additionalBranchIds: editingEmployee.additionalBranchIds,
            status: editingEmployee.status,
          }}
          roles={roleOptions}
          branches={branchOptions}
          onSubmit={handleUpdate}
          title="Изменить сотрудника"
          showStatus
        />
      )}

      {inviteEmployee && (
        <InviteCodeDialog
          employeeId={inviteEmployee._id}
          fullName={inviteEmployee.fullName}
          code={inviteEmployee.inviteCode}
          open={inviteFor !== null}
          onOpenChange={(open) => !open && setInviteFor(null)}
        />
      )}
    </div>
  );
}
