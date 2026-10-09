import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  savePayrollAdjustment,
  savePayrollPosition,
  savePayrollPunch,
  upsertAttendanceRate,
} from "@/api/attendance.ts";

type RateInput = {
  employeeId: string;
  name: string;
  /** Ставка за час */
  rate: number;
  currency: string;
};

export function usePayrollMutations() {
  const qc = useQueryClient();
  const refresh = () => qc.invalidateQueries({ queryKey: ["attendance-payroll"] });
  const fail = () => toast.error("Не удалось сохранить изменения");

  const punch = useMutation({
    mutationFn: savePayrollPunch,
    onSuccess: refresh,
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

  return { punch, adjustment, position, rate };
}
