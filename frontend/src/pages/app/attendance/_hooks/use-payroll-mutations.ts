import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  savePayrollAdjustment,
  savePayrollPosition,
  savePayrollPunch,
} from "@/api/attendance.ts";

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

  return { punch, adjustment, position };
}
