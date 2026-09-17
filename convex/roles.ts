import { mutation, query } from "./_generated/server";
import type { MutationCtx } from "./_generated/server";
import { requireManager } from "./permissions";

// Default roles from the MADO Checklist spec (section 3.1 / 13.3).
// level: 0 = staff, 1 = manager, 2 = supervisor, 3 = director.
const DEFAULT_ROLES = [
  { code: "waiter", nameRu: "Официант", category: "staff" as const, level: 0 },
  { code: "runner", nameRu: "Раннер", category: "staff" as const, level: 0 },
  { code: "hostess", nameRu: "Хостес", category: "staff" as const, level: 0 },
  { code: "bartender", nameRu: "Бармен", category: "staff" as const, level: 0 },
  { code: "cashier", nameRu: "Кассир", category: "staff" as const, level: 0 },
  { code: "cook", nameRu: "Повар", category: "staff" as const, level: 0 },
  {
    code: "confectioner",
    nameRu: "Кондитер",
    category: "staff" as const,
    level: 0,
  },
  { code: "cleaner", nameRu: "Уборщик", category: "staff" as const, level: 0 },
  {
    code: "manager",
    nameRu: "Менеджер",
    category: "management" as const,
    level: 1,
  },
  {
    code: "senior_manager",
    nameRu: "Старший менеджер",
    category: "management" as const,
    level: 1,
  },
  {
    code: "supervisor",
    nameRu: "Управляющий",
    category: "management" as const,
    level: 2,
  },
  {
    code: "director",
    nameRu: "Директор",
    category: "management" as const,
    level: 3,
  },
];

// Idempotent: inserts any default role missing from the table. Cheap (12
// indexed lookups), safe to call from any mutation that depends on roles
// existing.
export async function ensureDefaultRoles(ctx: MutationCtx): Promise<void> {
  for (const role of DEFAULT_ROLES) {
    const existing = await ctx.db
      .query("roles")
      .withIndex("by_code", (q) => q.eq("code", role.code))
      .unique();
    if (!existing) {
      await ctx.db.insert("roles", role);
    }
  }
}

export const seedDefaultRoles = mutation({
  args: {},
  handler: async (ctx) => {
    await ensureDefaultRoles(ctx);
    return null;
  },
});

export const listRoles = query({
  args: {},
  handler: async (ctx) => {
    await requireManager(ctx);
    return await ctx.db.query("roles").collect();
  },
});
