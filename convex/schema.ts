import { defineSchema } from "convex/server";
import { v } from "convex/values";
import { defineTable } from "convex/server";
import { branches } from "./schema/branches";
import { roles } from "./schema/roles";
import { employees, employeeAccounts } from "./schema/employees";

export default defineSchema({
  users: defineTable({
    tokenIdentifier: v.string(),
    name: v.optional(v.string()),
    email: v.optional(v.string()),
  }).index("by_token", ["tokenIdentifier"]),

  branches,
  roles,
  employees,
  employeeAccounts,
});
