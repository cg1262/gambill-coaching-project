import { z } from "zod";

export const ColumnDefSchema = z.object({
  name: z.string().min(1),
  dataType: z.enum(["string", "int", "bigint", "decimal", "boolean", "date", "timestamp", "json", "array", "struct"]),
  nullable: z.boolean(),
  isPrimaryKey: z.boolean().optional(),
});

export const TableNodeSchema = z.object({
  id: z.string().min(1),
  schema: z.string().min(1),
  table: z.string().min(1),
  columns: z.array(ColumnDefSchema).min(1),
  source: z.enum(["mock", "unity_catalog"]),
  position: z.object({ x: z.number(), y: z.number() }),
});

export const RelationshipSchema = z.object({
  id: z.string(),
  fromTableId: z.string(),
  toTableId: z.string(),
  fromColumn: z.string(),
  toColumn: z.string(),
  joinColumns: z.array(z.object({ fromColumn: z.string(), toColumn: z.string() })).optional(),
  relationshipType: z.enum(["one_to_one", "one_to_many", "many_to_one", "many_to_many"]),
});

export const CanvasAstSchema = z.object({
  version: z.literal("1.0"),
  workspaceId: z.string(),
  tables: z.array(TableNodeSchema),
  relationships: z.array(RelationshipSchema),
  modifiedTableIds: z.array(z.string()).optional(),
});
