import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  listBranches,
  createBranch,
  updateBranch,
  deactivateBranch,
} from "@/api/branches.ts";
import type { Branch, BranchCreate } from "@/api/branches.ts";
import { Building2, MapPin, Plus, Pencil, Clock } from "lucide-react";

type BranchFormValue = {
  name: string;
  address: string;
  city: string;
  timezone: string;
};

const EMPTY_FORM: BranchFormValue = {
  name: "",
  address: "",
  city: "",
  timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
};

function BranchDialog({
  open,
  onClose,
  initial,
  onSubmit,
  title,
}: {
  open: boolean;
  onClose: () => void;
  initial: BranchFormValue;
  onSubmit: (value: BranchFormValue) => Promise<void>;
  title: string;
}) {
  const [value, setValue] = useState(initial);
  const [submitting, setSubmitting] = useState(false);

  if (!open) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
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
      <div className="w-full max-w-md rounded-2xl border bg-card shadow-xl">
        <div className="flex items-center justify-between border-b px-5 py-4">
          <h2 className="text-lg font-semibold">{title}</h2>
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground text-xl">✕</button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4 p-5">
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Название</label>
            <input
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
              value={value.name}
              onChange={(e) => setValue((v) => ({ ...v, name: e.target.value }))}
              placeholder="Tashkent City Mall"
              required
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Город</label>
            <input
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
              value={value.city}
              onChange={(e) => setValue((v) => ({ ...v, city: e.target.value }))}
              placeholder="Ташкент"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Адрес</label>
            <input
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
              value={value.address}
              onChange={(e) => setValue((v) => ({ ...v, address: e.target.value }))}
              placeholder="ул. Амира Темура, 1"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Часовой пояс</label>
            <input
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
              value={value.timezone}
              onChange={(e) => setValue((v) => ({ ...v, timezone: e.target.value }))}
              placeholder="Asia/Tashkent"
              required
            />
          </div>
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

export default function BranchesPage() {
  const qc = useQueryClient();
  const { data: branches, isLoading } = useQuery({ queryKey: ["branches"], queryFn: listBranches });
  const createMut = useMutation({ mutationFn: (d: BranchCreate) => createBranch(d), onSuccess: () => qc.invalidateQueries({ queryKey: ["branches"] }) });
  const updateMut = useMutation({ mutationFn: ({ id, d }: { id: number; d: BranchCreate }) => updateBranch(id, d), onSuccess: () => qc.invalidateQueries({ queryKey: ["branches"] }) });
  const deactivateMut = useMutation({ mutationFn: deactivateBranch, onSuccess: () => qc.invalidateQueries({ queryKey: ["branches"] }) });

  const [createOpen, setCreateOpen] = useState(false);
  const [editing, setEditing] = useState<Branch | null>(null);

  const handleCreate = async (v: BranchFormValue) => {
    try {
      await createMut.mutateAsync({ name: v.name, address: v.address || undefined, city: v.city || undefined, timezone: v.timezone });
      toast.success("Филиал создан");
    } catch {
      toast.error("Не удалось создать филиал");
      throw new Error("create failed");
    }
  };

  const handleUpdate = async (v: BranchFormValue) => {
    if (!editing) return;
    try {
      await updateMut.mutateAsync({ id: editing.id, d: { name: v.name, address: v.address || undefined, city: v.city || undefined, timezone: v.timezone } });
      toast.success("Филиал обновлён");
    } catch {
      toast.error("Не удалось обновить филиал");
      throw new Error("update failed");
    }
  };

  const handleDeactivate = async (id: number) => {
    try {
      await deactivateMut.mutateAsync(id);
      toast.success("Филиал деактивирован");
    } catch {
      toast.error("Не удалось деактивировать");
    }
  };

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-4 md:p-8">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Филиалы</h1>
          <p className="text-sm text-muted-foreground">Управляйте филиалами сети ресторанов MADO</p>
        </div>
        <button
          type="button"
          onClick={() => setCreateOpen(true)}
          className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90"
        >
          <Plus className="size-4" />Филиал
        </button>
      </div>

      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2">
          {Array.from({ length: 2 }).map((_, i) => (
            <div key={i} className="h-32 animate-pulse rounded-xl border bg-muted" />
          ))}
        </div>
      ) : !branches || branches.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed py-16 text-center">
          <Building2 className="size-10 text-muted-foreground" />
          <p className="font-semibold">Нет филиалов</p>
          <p className="text-sm text-muted-foreground">Создайте первый филиал, чтобы начать</p>
          <button type="button" onClick={() => setCreateOpen(true)} className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90">Создать филиал</button>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {branches.map((branch) => (
            <div key={branch.id} className="rounded-xl border bg-card p-5 shadow-sm space-y-3">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="font-semibold truncate">{branch.name}</p>
                  {branch.city && (
                    <span className="inline-flex items-center gap-1 mt-1 rounded-full bg-secondary px-2 py-0.5 text-xs text-secondary-foreground">
                      <MapPin className="size-3" />{branch.city}
                    </span>
                  )}
                </div>
                <button type="button" onClick={() => setEditing(branch)} className="text-muted-foreground hover:text-foreground rounded p-1">
                  <Pencil className="size-4" />
                </button>
              </div>
              {branch.address && <p className="text-sm text-muted-foreground text-balance">{branch.address}</p>}
              <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
                <Clock className="size-3.5" />{branch.timezone}
              </p>
              <button
                type="button"
                onClick={() => handleDeactivate(branch.id)}
                className="rounded-lg border px-3 py-1.5 text-sm hover:bg-muted"
              >
                Деактивировать
              </button>
            </div>
          ))}
        </div>
      )}

      <BranchDialog open={createOpen} onClose={() => setCreateOpen(false)} initial={EMPTY_FORM} onSubmit={handleCreate} title="Новый филиал" />
      {editing && (
        <BranchDialog
          open
          onClose={() => setEditing(null)}
          initial={{ name: editing.name, address: editing.address ?? "", city: editing.city ?? "", timezone: editing.timezone }}
          onSubmit={handleUpdate}
          title="Изменить филиал"
        />
      )}
    </div>
  );
}
