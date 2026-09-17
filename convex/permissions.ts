import { ConvexError } from "convex/values";
import type { Id } from "./_generated/dataModel";
import type { MutationCtx, QueryCtx } from "./_generated/server";

// Permission levels, mirrors convex/schema/roles.ts `level` field.
export const STAFF_LEVEL = 0;
export const MANAGER_LEVEL = 1;
export const SUPERVISOR_LEVEL = 2;
export const DIRECTOR_LEVEL = 3;

export type CurrentEmployee = {
  userId: Id<"users">;
  employeeId: Id<"employees">;
  fullName: string;
  roleId: Id<"roles">;
  roleCode: string;
  roleLevel: number;
  primaryBranchId: Id<"branches">;
  additionalBranchIds: Array<Id<"branches">>;
  status: "active" | "inactive" | "fired";
};

// Resolves the signed-in Hercules Auth user to their employee profile.
// Throws if not authenticated or if no employee profile has been linked yet.
export async function getCurrentEmployee(
  ctx: QueryCtx | MutationCtx,
): Promise<CurrentEmployee> {
  const identity = await ctx.auth.getUserIdentity();
  if (!identity) {
    throw new ConvexError({
      code: "UNAUTHENTICATED",
      message: "User not logged in",
    });
  }

  const user = await ctx.db
    .query("users")
    .withIndex("by_token", (q) => q.eq("tokenIdentifier", identity.tokenIdentifier))
    .unique();
  if (!user) {
    throw new ConvexError({ code: "NOT_FOUND", message: "User not found" });
  }

  const account = await ctx.db
    .query("employeeAccounts")
    .withIndex("by_user", (q) => q.eq("userId", user._id))
    .unique();
  if (!account) {
    throw new ConvexError({
      code: "FORBIDDEN",
      message: "No employee profile linked to this account",
    });
  }

  const employee = await ctx.db.get("employees", account.employeeId);
  if (!employee) {
    throw new ConvexError({ code: "NOT_FOUND", message: "Employee not found" });
  }

  const role = await ctx.db.get("roles", employee.roleId);
  if (!role) {
    throw new ConvexError({ code: "NOT_FOUND", message: "Role not found" });
  }

  return {
    userId: user._id,
    employeeId: employee._id,
    fullName: employee.fullName,
    roleId: role._id,
    roleCode: role.code,
    roleLevel: role.level,
    primaryBranchId: employee.primaryBranchId,
    additionalBranchIds: employee.additionalBranchIds,
    status: employee.status,
  };
}

// Same as getCurrentEmployee, but returns null instead of throwing when the
// user has no linked employee profile yet (e.g. right after sign-in).
export async function tryGetCurrentEmployee(
  ctx: QueryCtx | MutationCtx,
): Promise<CurrentEmployee | null> {
  try {
    return await getCurrentEmployee(ctx);
  } catch {
    return null;
  }
}

export async function requireMinLevel(
  ctx: QueryCtx | MutationCtx,
  minLevel: number,
): Promise<CurrentEmployee> {
  const employee = await getCurrentEmployee(ctx);
  if (employee.roleLevel < minLevel) {
    throw new ConvexError({
      code: "FORBIDDEN",
      message: "Insufficient permissions",
    });
  }
  return employee;
}

// Manager, senior manager, supervisor, or director.
export async function requireManager(ctx: QueryCtx | MutationCtx) {
  return requireMinLevel(ctx, MANAGER_LEVEL);
}

// Supervisor or director: can see/manage all branches.
export async function requireSupervisor(ctx: QueryCtx | MutationCtx) {
  return requireMinLevel(ctx, SUPERVISOR_LEVEL);
}

export function canAccessAllBranches(employee: CurrentEmployee): boolean {
  return employee.roleLevel >= SUPERVISOR_LEVEL;
}

export function canAccessBranch(
  employee: CurrentEmployee,
  branchId: Id<"branches">,
): boolean {
  if (canAccessAllBranches(employee)) {
    return true;
  }
  return (
    employee.primaryBranchId === branchId ||
    employee.additionalBranchIds.includes(branchId)
  );
}
