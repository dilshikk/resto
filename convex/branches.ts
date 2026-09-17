import { ConvexError, v } from "convex/values";
import { mutation, query } from "./_generated/server";
import { canAccessAllBranches, requireSupervisor, tryGetCurrentEmployee } from "./permissions";

export const listBranches = query({
  args: {},
  handler: async (ctx) => {
    const employee = await tryGetCurrentEmployee(ctx);
    const branches = await ctx.db.query("branches").collect();
    const active = branches.filter((b) => b.isActive);

    if (!employee) {
      return active;
    }
    if (canAccessAllBranches(employee)) {
      return active;
    }
    const allowed = new Set([
      employee.primaryBranchId,
      ...employee.additionalBranchIds,
    ]);
    return active.filter((b) => allowed.has(b._id));
  },
});

export const createBranch = mutation({
  args: {
    name: v.string(),
    address: v.optional(v.string()),
    city: v.optional(v.string()),
    timezone: v.string(),
  },
  handler: async (ctx, args) => {
    await requireSupervisor(ctx);
    const name = args.name.trim();
    if (!name) {
      throw new ConvexError({ code: "BAD_REQUEST", message: "Название филиала обязательно" });
    }
    return await ctx.db.insert("branches", {
      name,
      address: args.address?.trim() || undefined,
      city: args.city?.trim() || undefined,
      timezone: args.timezone,
      isActive: true,
    });
  },
});

export const updateBranch = mutation({
  args: {
    branchId: v.id("branches"),
    name: v.string(),
    address: v.optional(v.string()),
    city: v.optional(v.string()),
    timezone: v.string(),
  },
  handler: async (ctx, args) => {
    await requireSupervisor(ctx);
    const branch = await ctx.db.get("branches", args.branchId);
    if (!branch) {
      throw new ConvexError({ code: "NOT_FOUND", message: "Филиал не найден" });
    }
    const name = args.name.trim();
    if (!name) {
      throw new ConvexError({ code: "BAD_REQUEST", message: "Название филиала обязательно" });
    }
    await ctx.db.patch("branches", args.branchId, {
      name,
      address: args.address?.trim() || undefined,
      city: args.city?.trim() || undefined,
      timezone: args.timezone,
    });
    return null;
  },
});

export const deactivateBranch = mutation({
  args: { branchId: v.id("branches") },
  handler: async (ctx, args) => {
    await requireSupervisor(ctx);
    const branch = await ctx.db.get("branches", args.branchId);
    if (!branch) {
      throw new ConvexError({ code: "NOT_FOUND", message: "Филиал не найден" });
    }
    await ctx.db.patch("branches", args.branchId, { isActive: false });
    return null;
  },
});
