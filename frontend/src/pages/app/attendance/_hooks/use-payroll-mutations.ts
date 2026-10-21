import { useMutation, useQueryClient } from "@tanstack/react-query";
import { isAxiosError } from "axios";
import { toast } from "sonner";
import {
  savePayrollAdjustment,
  savePayrollLink,
  savePayrollPlan,
  savePayrollPosition,
  savePayrollPunch,
  savePayrollTermination,
  saveShiftFine,
  upsertAttendanceRate,
} from "@/api/attendance.ts";

type RateInput = {
  employeeId: string;
  name: string;
  /** Ставка за час */
  rate: number;
  currency: string;
};

// Текст ошибки с сервера, если он есть (например «сотрудник уже привязан»)
function errorText(error: unknown): string {
  if (isAxiosError(error)) {
    const detail: unknown = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
  }
  return "Не удалось сохранить изменения";
}

export function usePayrollMutations() {
  const qc = useQueryClient();
  const refresh = () => qc.invalidateQueries({ queryKey: ["attendance-payroll"] });
  const fail = (error: unknown) => toast.error(errorText(error));

  const punch = useMutation({
    mutationFn: savePayrollPunch,
    onSuccess: refresh,
    onError: fail,
  });
  const shiftFine = useMutation({
    mutationFn: saveShiftFine,
    onSuccess: refresh,
    onError: fail,
  });
  const plan = useMutation({
    mutationFn: savePayrollPlan,
    onSuccess: refresh,
    onError: fail,
  });
  const link = useMutation({
    mutationFn: savePayrollLink,
    onSuccess: () => {
      void refresh();
      toast.success("Привязка сохранена");
    },
    onError: fail,
  });
  const adjustment = useMutation({
    mutationFn: savePayrollAdjustment,
    onSuccess: refresh,
    onError: fail,
  });
  const position = useMutation({
    mutationFn: savePayrollPosition,
    onSuccess: refresh,
    onError: fail,
  });
  const termination = useMutation({
    mutationFn: savePayrollTermination,
    onSuccess: (_data, variables) => {
      void refresh();
      toast.success(variables.terminated_from ? "Сотрудник уволен" : "Сотрудник восстановлен");
    },
    onError: fail,
  });
  const rate = useMutation({
    mutationFn: (input: RateInput) =>
      upsertAttendanceRate(input.employeeId, {
        display_name: input.name,
        rate_per_shift: input.rate,
        currency: input.currency,
      }),
    onSuccess: () => {
      void refresh();
      void qc.invalidateQueries({ queryKey: ["attendance-employees"] });
    },
    onError: fail,
  });

  return { punch, shiftFine, plan, link, adjustment, position, termination, rate };
}
