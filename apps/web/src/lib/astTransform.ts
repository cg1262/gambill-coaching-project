import type { Edge, Node } from "reactflow";
import type { CanvasAST, ColumnDef, EditableNodeData } from "./types";
import { CanvasAstSchema } from "./schemas";

const fallbackColumns: ColumnDef[] = [
  { name: "id", dataType: "string", nullable: false, isPrimaryKey: true },
  { name: "name", dataType: "string", nullable: true },
];

export function toCanvasAST(nodes: Node[], edges: Edge[], workspaceId = "demo-workspace"): CanvasAST {
  const ast: CanvasAST = {
    version: "1.0",
    workspaceId,
    tables: nodes.map((n) => {
      const d = (n.data ?? {}) as EditableNodeData;
      return {
      id: n.id,
      schema: d.schema ?? "demo",
      table: String(d.label ?? n.id),
      columns: d.columns?.length ? d.columns : fallbackColumns,
      source: "mock",
      position: n.position,
    }}),
    relationships: edges.map((e) => {
      const d = (e.data ?? {}) as any;
      const joins = Array.isArray(d.joinColumns) && d.joinColumns.length
        ? d.joinColumns
            .map((j: any) => ({ fromColumn: String(j.fromColumn || "").trim(), toColumn: String(j.toColumn || "").trim() }))
            .filter((j: any) => j.fromColumn && j.toColumn)
        : [];
      return {
        id: e.id,
        fromTableId: String(e.source),
        toTableId: String(e.target),
        fromColumn: joins[0]?.fromColumn || String(d.fromColumn || "id"),
        toColumn: joins[0]?.toColumn || String(d.toColumn || "id"),
        joinColumns: joins.length ? joins : undefined,
        relationshipType: (String(e.label || d.relationshipType || "many_to_one") as any),
      };
    }),
    modifiedTableIds: nodes.length ? [nodes[0].id] : [],
  };

  return CanvasAstSchema.parse(ast);
}
