import { useQuery } from "@tanstack/react-query";
import { listBranches } from "@/api/branches.ts";
import { listEmployees, getMyProfile } from "@/api/employees.ts";
import { Building2, Users, ClipboardList } from "lucide-react";

export default function DashboardPage() {
  const { data: profile } = useQuery({ queryKey: ["my-profile"], queryFn: getMyProfile });
  const { data: branches, isLoading: branchesLoading } = useQuery({
    queryKey: ["branches"],
    queryFn: listBranches,
  });
  const { data: employees, isLoading: employeesLoading } = useQuery({
    queryKey: ["employees"],
    queryFn: () => listEmployees(),
  });

  const loading = branchesLoading || employeesLoading;

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-4 md:p-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          {profile ? `Здравствуйте, ${profile.full_name.split(" ")[0]}` : "Дашборд"}
        </h1>
        <p className="text-sm text-muted-foreground">Обзор системы MADO Checklist</p>
      </div>

      {loading ? (
        <div className="grid gap-4 sm:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-28 w-full animate-pulse rounded-xl border bg-muted" />
          ))}
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="rounded-xl border bg-card p-5 shadow-sm">
            <div className="flex items-center gap-3 mb-3">
              <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <Building2 className="size-5" />
              </div>
              <span className="font-semibold text-base">Филиалы</span>
            </div>
            <p className="text-3xl font-bold">{branches?.length ?? 0}</p>
          </div>
          <div className="rounded-xl border bg-card p-5 shadow-sm">
            <div className="flex items-center gap-3 mb-3">
              <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <Users className="size-5" />
              </div>
              <span className="font-semibold text-base">Сотрудники</span>
            </div>
            <p className="text-3xl font-bold">{employees?.length ?? 0}</p>
          </div>
          <div className="rounded-xl border bg-card p-5 shadow-sm">
            <div className="flex items-center gap-3 mb-3">
              <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <ClipboardList className="size-5" />
              </div>
              <span className="font-semibold text-base">Чек-листы сегодня</span>
            </div>
            <p className="text-3xl font-bold text-muted-foreground">—</p>
            <p className="text-xs text-muted-foreground mt-1">Появится в следующем этапе</p>
          </div>
        </div>
      )}
    </div>
  );
}
