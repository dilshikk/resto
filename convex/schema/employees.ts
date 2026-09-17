import { defineTable } from "convex/server";
import { v } from "convex/values";

// Employee business profile (created by managers). Not linked to a platform
// account until the employee claims their profile with the invite code.
export const employees = defineTable({
  fullName: v.string(),
  phone: v.optional(v.string()),
  roleId: v.id("roles"),
  status: v.union(
    v.literal("active"),
    v.literal("inactive"),
    v.literal("fired"),
  ),
  // Always present (never optional) so it can be indexed. Single-use.
  inviteCode: v.string(),
  primaryBranchId: v.id("branches"),
  // Small, bounded list of extra branches this employee can also work at.
  additionalBranchIds: v.array(v.id("branches")),
  hiredAt: v.optional(v.string()),
})
  .index("by_invite_code", ["inviteCode"])
  .index("by_role", ["roleId"])
  .index("by_branch", ["primaryBranchId"])
  .index("by_status", ["status"]);

// Links a platform user account (Hercules Auth) to an employee profile.
// Kept as its own table so both foreign keys can be indexed (Convex forbids
// indexing optional fields, and not every employee has claimed an account yet).
export const employeeAccounts = defineTable({
  employeeId: v.id("employees"),
  userId: v.id("users"),
})
  .index("by_user", ["userId"])
  .index("by_employee", ["employeeId"]);
