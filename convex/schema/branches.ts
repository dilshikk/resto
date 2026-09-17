import { defineTable } from "convex/server";
import { v } from "convex/values";

// Restaurant branches (filials). Small table, no special indexes needed yet.
export const branches = defineTable({
  name: v.string(),
  address: v.optional(v.string()),
  city: v.optional(v.string()),
  timezone: v.string(),
  isActive: v.boolean(),
});
