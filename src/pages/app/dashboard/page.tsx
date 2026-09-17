import { useQuery } from "convex/react";
import { api } from "@/convex/_generated/api.js";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card.tsx";
import { Skeleton } from "@/components/ui/skeleton.tsx";
import { Building2, Users, ClipboardList } from "lucide-react";

export default function DashboardPage() {
  const profile = useQuery(api.employees.getMyEmployeeProfile, {});
  const branches = useQuery(api.branches.listBranches, {});
  const employees = useQuery(api.employees.listEmployees, {});

  const loading = profile === undefined || branches === undefined || employees === undefined;

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-4 md:p-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          {profile ? `Здравствуйте, ${profile.fullName.split(" ")[0]}` : "Дашборд"}
        </h1>
        <p className="text-sm text-muted-foreground">Обзор системы MADO Checklist</p>
      </div>

      {loading ? (
        <div className="grid gap-4 sm:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-28 w-full" />
          ))}
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-3">
          <Card>
            <CardHeader className="flex flex-row items-center gap-3">
              <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <Building2 className="size-5" />
              </div>
              <CardTitle className="text-base">Филиалы</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-bold">{branches.length}</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center gap-3">
              <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <Users className="size-5" />
              </div>
              <CardTitle className="text-base">Сотрудники</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-bold">{employees.length}</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center gap-3">
              <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <ClipboardList className="size-5" />
              </div>
              <CardTitle className="text-base">Чек-листы сегодня</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-bold text-muted-foreground">—</p>
              <p className="text-xs text-muted-foreground">Появится в следующем этапе</p>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
