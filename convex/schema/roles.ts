import { defineTable } from "convex/server";
import { v } from "convex/values";

// Job roles / positions (waiter, cook, manager, director, etc).
// `level` drives permission checks: 0 = staff, 1 = manager, 2 = supervisor, 3 = director.
export const roles = defineTable({
  code: v.string(),
  nameRu: v.string(),
  nameUz: v.optional(v.string()),
  nameEn: v.optional(v.string()),
  nameTr: v.optional(v.string()),
  category: v.union(v.literal("staff"), v.literal("management")),
  level: v.number(),
}).index("by_code", ["code"]);
