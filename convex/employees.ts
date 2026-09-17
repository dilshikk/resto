import { ConvexError, v } from "convex/values";
import { mutation, query } from "./_generated/server";
import type { Doc, Id } from "./_generated/dataModel";
import { canAccessAllBranches, canAccessBranch, requireManager } from "./permissions";

function generateInviteCode(): string {
  // Short, human-typeable code the employee enters once to claim their profile.
  const chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  let code = "";
  for (let i = 0; i < 8; i++) {
    code += chars[Math.floor(Math.random() * chars.length)];
  }
  return code;
}

export const listEmployees = query({
  args: { branchId: v.optional(v.id("branches")) },
  handler: async (ctx, args) => {
    const currentEmployee = await requireManager(ctx);

    const all = await ctx.db.query("employees").collect();
    const visible = all.filter((e) => {
      if (args.branchId) {
        if (!canAccessBranch(currentEmployee, args.branchId)) {
          throw new ConvexError({ code: "FORBIDDEN", message: "Нет доступа к этому филиалу" });
        }
        return (
          e.primaryBranchId === args.branchId ||
          e.additionalBranchIds.includes(args.branchId)
        );
      }
      if (canAccessAllBranches(currentEmployee)) {
        return true;
      }
      return (
        e.primaryBranchId === currentEmployee.primaryBranchId ||
        e.additionalBranchIds.includes(currentEmployee.primaryBranchId)
      );
    });

    const roleIds = [...new Set(visible.map((e) => e.roleId))];
    const roles = await Promise.all(roleIds.map((id) => ctx.db.get("roles", id)));
    const roleById = new Map(roles.filter((r): r is Doc<"roles"> => r !== null).map((r) => [r._id, r]));

    const branchIds = [...new Set(visible.map((e) => e.primaryBranchId))];
    const branchesList = await Promise.all(branchIds.map((id) => ctx.db.get("branches", id)));
    const branchById = new Map(
      branchesList.filter((b): b is Doc<"branches"> => b !== null).map((b) => [b._id, b]),
    );

    const accounts = await ctx.db.query("employeeAccounts").collect();
    const claimedEmployeeIds = new Set(accounts.map((a) => a.employeeId));

    return visible.map((e) => ({
      _id: e._id,
      _creationTime: e._creationTime,
      fullName: e.fullName,
      phone: e.phone,
      status: e.status,
      inviteCode: e.inviteCode,
      hasClaimedAccount: claimedEmployeeIds.has(e._id),
      roleId: e.roleId,
      roleName: roleById.get(e.roleId)?.nameRu ?? "—",
      roleLevel: roleById.get(e.roleId)?.level ?? 0,
      primaryBranchId: e.primaryBranchId,
      primaryBranchName: branchById.get(e.primaryBranchId)?.name ?? "—",
      additionalBranchIds: e.additionalBranchIds,
      hiredAt: e.hiredAt,
    }));
  },
});

export const createEmployee = mutation({
  args: {
    fullName: v.string(),
    phone: v.optional(v.string()),
    roleId: v.id("roles"),
    primaryBranchId: v.id("branches"),
    additionalBranchIds: v.array(v.id("branches")),
    hiredAt: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const currentEmployee = await requireManager(ctx);
    if (!canAccessBranch(currentEmployee, args.primaryBranchId)) {
      throw new ConvexError({ code: "FORBIDDEN", message: "Нет доступа к этому филиалу" });
    }
    const fullName = args.fullName.trim();
    if (!fullName) {
      throw new ConvexError({ code: "BAD_REQUEST", message: "ФИО обязательно" });
    }
    const role = await ctx.db.get("roles", args.roleId);
    if (!role) {
      throw new ConvexError({ code: "NOT_FOUND", message: "Должность не найдена" });
    }
    const branch = await ctx.db.get("branches", args.primaryBranchId);
    if (!branch) {
      throw new ConvexError({ code: "NOT_FOUND", message: "Филиал не найден" });
    }

    let inviteCode = generateInviteCode();
    // Extremely unlikely collision, guard anyway since the field is unique-ish via index lookup.
    for (let attempts = 0; attempts < 5; attempts++) {
      const existing = await ctx.db
        .query("employees")
        .withIndex("by_invite_code", (q) => q.eq("inviteCode", inviteCode))
        .unique();
      if (!existing) break;
      inviteCode = generateInviteCode();
    }

    return await ctx.db.insert("employees", {
      fullName,
      phone: args.phone?.trim() || undefined,
      roleId: args.roleId,
      status: "active",
      inviteCode,
      primaryBranchId: args.primaryBranchId,
      additionalBranchIds: args.additionalBranchIds,
      hiredAt: args.hiredAt,
    });
  },
});

export const updateEmployee = mutation({
  args: {
    employeeId: v.id("employees"),
    fullName: v.string(),
    phone: v.optional(v.string()),
    roleId: v.id("roles"),
    primaryBranchId: v.id("branches"),
    additionalBranchIds: v.array(v.id("branches")),
    status: v.union(v.literal("active"), v.literal("inactive"), v.literal("fired")),
  },
  handler: async (ctx, args) => {
    const currentEmployee = await requireManager(ctx);
    const employee = await ctx.db.get("employees", args.employeeId);
    if (!employee) {
      throw new ConvexError({ code: "NOT_FOUND", message: "Сотрудник не найден" });
    }
    if (
      !canAccessBranch(currentEmployee, employee.primaryBranchId) ||
      !canAccessBranch(currentEmployee, args.primaryBranchId)
    ) {
      throw new ConvexError({ code: "FORBIDDEN", message: "Нет доступа к этому филиалу" });
    }
    const fullName = args.fullName.trim();
    if (!fullName) {
      throw new ConvexError({ code: "BAD_REQUEST", message: "ФИО обязательно" });
    }
    await ctx.db.patch("employees", args.employeeId, {
      fullName,
      phone: args.phone?.trim() || undefined,
      roleId: args.roleId,
      primaryBranchId: args.primaryBranchId,
      additionalBranchIds: args.additionalBranchIds,
      status: args.status,
    });
    return null;
  },
});

export const regenerateInviteCode = mutation({
  args: { employeeId: v.id("employees") },
  handler: async (ctx, args) => {
    await requireManager(ctx);
    const employee = await ctx.db.get("employees", args.employeeId);
    if (!employee) {
      throw new ConvexError({ code: "NOT_FOUND", message: "Сотрудник не найден" });
    }
    const newCode = generateInviteCode();
    await ctx.db.patch("employees", args.employeeId, { inviteCode: newCode });
    return newCode;
  },
});

// Called once by a newly signed-in Hercules Auth user to link their account
// to the employee profile created for them by a manager.
export const claimEmployeeProfile = mutation({
  args: { inviteCode: v.string() },
  handler: async (ctx, args) => {
    const identity = await ctx.auth.getUserIdentity();
    if (!identity) {
      throw new ConvexError({ code: "UNAUTHENTICATED", message: "User not logged in" });
    }
    const user = await ctx.db
      .query("users")
      .withIndex("by_token", (q) => q.eq("tokenIdentifier", identity.tokenIdentifier))
      .unique();
    if (!user) {
      throw new ConvexError({ code: "NOT_FOUND", message: "User not found" });
    }

    const existingAccount = await ctx.db
      .query("employeeAccounts")
      .withIndex("by_user", (q) => q.eq("userId", user._id))
      .unique();
    if (existingAccount) {
      throw new ConvexError({
        code: "CONFLICT",
        message: "К этому аккаунту уже привязан профиль сотрудника",
      });
    }

    const code = args.inviteCode.trim().toUpperCase();
    const employee = await ctx.db
      .query("employees")
      .withIndex("by_invite_code", (q) => q.eq("inviteCode", code))
      .unique();
    if (!employee) {
      throw new ConvexError({ code: "NOT_FOUND", message: "Код приглашения не найден" });
    }
    if (employee.status !== "active") {
      throw new ConvexError({ code: "FORBIDDEN", message: "Сотрудник деактивирован" });
    }

    const alreadyClaimed = await ctx.db
      .query("employeeAccounts")
      .withIndex("by_employee", (q) => q.eq("employeeId", employee._id))
      .unique();
    if (alreadyClaimed) {
      throw new ConvexError({
        code: "CONFLICT",
        message: "Этот профиль сотрудника уже привязан к другому аккаунту",
      });
    }

    await ctx.db.insert("employeeAccounts", {
      employeeId: employee._id,
      userId: user._id,
    });
    return null;
  },
});

export const getMyEmployeeProfile = query({
  args: {},
  handler: async (ctx) => {
    const identity = await ctx.auth.getUserIdentity();
    if (!identity) {
      return null;
    }
    const user = await ctx.db
      .query("users")
      .withIndex("by_token", (q) => q.eq("tokenIdentifier", identity.tokenIdentifier))
      .unique();
    if (!user) {
      return null;
    }
    const account = await ctx.db
      .query("employeeAccounts")
      .withIndex("by_user", (q) => q.eq("userId", user._id))
      .unique();
    if (!account) {
      return null;
    }
    const employee = await ctx.db.get("employees", account.employeeId);
    if (!employee) {
      return null;
    }
    const role = await ctx.db.get("roles", employee.roleId);
    const branch = await ctx.db.get("branches", employee.primaryBranchId);
    return {
      _id: employee._id,
      fullName: employee.fullName,
      status: employee.status,
      roleId: employee.roleId,
      roleName: role?.nameRu ?? "—",
      roleCode: role?.code ?? "",
      roleLevel: role?.level ?? 0,
      primaryBranchId: employee.primaryBranchId,
      primaryBranchName: branch?.name ?? "—",
      additionalBranchIds: employee.additionalBranchIds,
    };
  },
});

// First-ever employee account created (bootstrap): makes the current user a
// director with no branch restrictions, so someone can start configuring the
// system. Only works while there are zero employees in the whole app.
export const bootstrapDirector = mutation({
  args: {
    fullName: v.string(),
    branchName: v.string(),
    timezone: v.string(),
  },
  handler: async (ctx, args) => {
    const identity = await ctx.auth.getUserIdentity();
    if (!identity) {
      throw new ConvexError({ code: "UNAUTHENTICATED", message: "User not logged in" });
    }
    const existingEmployees = await ctx.db.query("employees").take(1);
    if (existingEmployees.length > 0) {
      throw new ConvexError({
        code: "CONFLICT",
        message: "Система уже настроена. Обратитесь к директору за приглашением.",
      });
    }

    const user = await ctx.db
      .query("users")
      .withIndex("by_token", (q) => q.eq("tokenIdentifier", identity.tokenIdentifier))
      .unique();
    if (!user) {
      throw new ConvexError({ code: "NOT_FOUND", message: "User not found" });
    }

    let directorRole = await ctx.db
      .query("roles")
      .withIndex("by_code", (q) => q.eq("code", "director"))
      .unique();
    if (!directorRole) {
      const roleId = await ctx.db.insert("roles", {
        code: "director",
        nameRu: "Директор",
        category: "management",
        level: 3,
      });
      directorRole = await ctx.db.get("roles", roleId);
    }
    if (!directorRole) {
      throw new ConvexError({ code: "NOT_FOUND", message: "Не удалось создать роль директора" });
    }

    const branchName = args.branchName.trim() || "Главный филиал";
    const branchId = await ctx.db.insert("branches", {
      name: branchName,
      timezone: args.timezone,
      isActive: true,
    });

    const employeeId: Id<"employees"> = await ctx.db.insert("employees", {
      fullName: args.fullName.trim() || identity.name || "Директор",
      roleId: directorRole._id,
      status: "active",
      inviteCode: generateInviteCode(),
      primaryBranchId: branchId,
      additionalBranchIds: [],
    });

    await ctx.db.insert("employeeAccounts", { employeeId, userId: user._id });
    return null;
  },
});

export const hasAnyEmployees = query({
  args: {},
  handler: async (ctx) => {
    const rows = await ctx.db.query("employees").take(1);
    return rows.length > 0;
  },
});
