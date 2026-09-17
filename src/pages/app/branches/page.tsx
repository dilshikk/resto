import { useState } from "react";
import { useMutation, useQuery } from "convex/react";
import { ConvexError } from "convex/values";
import { toast } from "sonner";
import { api } from "@/convex/_generated/api.js";
import type { Id } from "@/convex/_generated/dataModel.d.ts";
import { Button } from "@/components/ui/button.tsx";
import { Input } from "@/components/ui/input.tsx";
import { Label } from "@/components/ui/label.tsx";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card.tsx";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog.tsx";
import { Skeleton } from "@/components/ui/skeleton.tsx";
import { Badge } from "@/components/ui/badge.tsx";
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty.tsx";
import { Building2, MapPin, Plus, Pencil, Clock } from "lucide-react";

function errorMessage(err: unknown, fallback: string) {
  if (err instanceof ConvexError) {
    const data = err.data as { message?: string };
    return data.message ?? fallback;
  }
  return fallback;
}

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

function BranchFormDialog({
  open,
  onOpenChange,
  initial,
  onSubmit,
  title,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initial: BranchFormValue;
  onSubmit: (value: BranchFormValue) => Promise<void>;
  title: string;
}) {
  const [value, setValue] = useState(initial);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
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
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="branch-name">Название</Label>
            <Input
              id="branch-name"
              value={value.name}
              onChange={(e) => setValue((v) => ({ ...v, name: e.target.value }))}
              placeholder="Tashkent City Mall"
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="branch-city">Город</Label>
            <Input
              id="branch-city"
              value={value.city}
              onChange={(e) => setValue((v) => ({ ...v, city: e.target.value }))}
              placeholder="Ташкент"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="branch-address">Адрес</Label>
            <Input
              id="branch-address"
              value={value.address}
              onChange={(e) => setValue((v) => ({ ...v, address: e.target.value }))}
              placeholder="ул. Амира Темура, 1"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="branch-timezone">Часовой пояс</Label>
            <Input
              id="branch-timezone"
              value={value.timezone}
              onChange={(e) => setValue((v) => ({ ...v, timezone: e.target.value }))}
              placeholder="Asia/Tashkent"
              required
            />
          </div>
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

export default function BranchesPage() {
  const branches = useQuery(api.branches.listBranches, {});
  const createBranch = useMutation(api.branches.createBranch);
  const updateBranch = useMutation(api.branches.updateBranch);
  const deactivateBranch = useMutation(api.branches.deactivateBranch);

  const [createOpen, setCreateOpen] = useState(false);
  const [editingId, setEditingId] = useState<Id<"branches"> | null>(null);

  const editingBranch = branches?.find((b) => b._id === editingId);

  const handleCreate = async (value: BranchFormValue) => {
    try {
      await createBranch({
        name: value.name,
        address: value.address || undefined,
        city: value.city || undefined,
        timezone: value.timezone,
      });
      toast.success("Филиал создан");
    } catch (err) {
      toast.error(errorMessage(err, "Не удалось создать филиал"));
      throw err;
    }
  };

  const handleUpdate = async (value: BranchFormValue) => {
    if (!editingId) return;
    try {
      await updateBranch({
        branchId: editingId,
        name: value.name,
        address: value.address || undefined,
        city: value.city || undefined,
        timezone: value.timezone,
      });
      toast.success("Филиал обновлён");
    } catch (err) {
      toast.error(errorMessage(err, "Не удалось обновить филиал"));
      throw err;
    }
  };

  const handleDeactivate = async (id: Id<"branches">) => {
    try {
      await deactivateBranch({ branchId: id });
      toast.success("Филиал деактивирован");
    } catch (err) {
      toast.error(errorMessage(err, "Не удалось деактивировать филиал"));
    }
  };

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-4 md:p-8">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Филиалы</h1>
          <p className="text-sm text-muted-foreground">
            Управляйте филиалами сети ресторанов MADO
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)} className="gap-2">
          <Plus className="size-4" />
          Филиал
        </Button>
      </div>

      {branches === undefined ? (
        <div className="grid gap-4 sm:grid-cols-2">
          {Array.from({ length: 2 }).map((_, i) => (
            <Skeleton key={i} className="h-32 w-full" />
          ))}
        </div>
      ) : branches.length === 0 ? (
        <Empty>
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <Building2 />
            </EmptyMedia>
            <EmptyTitle>Нет филиалов</EmptyTitle>
            <EmptyDescription>Создайте первый филиал, чтобы начать</EmptyDescription>
          </EmptyHeader>
          <EmptyContent>
            <Button size="sm" onClick={() => setCreateOpen(true)}>
              Создать филиал
            </Button>
          </EmptyContent>
        </Empty>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {branches.map((branch) => (
            <Card key={branch._id}>
              <CardHeader className="flex flex-row items-start justify-between gap-2">
                <div className="min-w-0">
                  <CardTitle className="truncate">{branch.name}</CardTitle>
                  {branch.city && (
                    <Badge variant="secondary" className="mt-1 gap-1">
                      <MapPin className="size-3" />
                      {branch.city}
                    </Badge>
                  )}
                </div>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  onClick={() => setEditingId(branch._id)}
                  aria-label="Редактировать"
                >
                  <Pencil className="size-4" />
                </Button>
              </CardHeader>
              <CardContent className="space-y-2 text-sm text-muted-foreground">
                {branch.address && <p className="text-balance">{branch.address}</p>}
                <p className="flex items-center gap-1.5">
                  <Clock className="size-3.5" />
                  {branch.timezone}
                </p>
                <div className="pt-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => handleDeactivate(branch._id)}
                  >
                    Деактивировать
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <BranchFormDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        initial={EMPTY_FORM}
        onSubmit={handleCreate}
        title="Новый филиал"
      />

      {editingBranch && (
        <BranchFormDialog
          open={editingId !== null}
          onOpenChange={(open) => !open && setEditingId(null)}
          initial={{
            name: editingBranch.name,
            address: editingBranch.address ?? "",
            city: editingBranch.city ?? "",
            timezone: editingBranch.timezone,
          }}
          onSubmit={handleUpdate}
          title="Изменить филиал"
        />
      )}
    </div>
  );
}
