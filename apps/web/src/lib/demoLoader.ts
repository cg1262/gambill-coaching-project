import type { Edge, Node } from "reactflow";

export type DemoKey = "telecom" | "cyber" | "manufacturing" | "aviation" | "star_schema" | "galaxy_schema" | "snowflake_schema";

type DemoAst = {
  tables: Array<{ id: string; schema: string; table: string; position: { x: number; y: number }; columns?: any[] }>;
  relationships: Array<{ id: string; fromTableId: string; toTableId: string; relationshipType: string }>;
};

export async function loadDemoToFlow(kind: DemoKey): Promise<{ nodes: Node[]; edges: Edge[]; raw: DemoAst }> {
  const res = await fetch(`/demo/${kind}_ast.json`);
  if (!res.ok) throw new Error(`Could not load ${kind} demo`);
  const raw = (await res.json()) as DemoAst;

  const nodes: Node[] = raw.tables.map((t) => ({
    id: t.id,
    type: "tableNode",
    position: t.position,
    data: { label: t.table, schema: t.schema, columns: t.columns ?? [] },
  }));

  const edges: Edge[] = raw.relationships.map((r) => ({
    id: r.id,
    source: r.fromTableId,
    target: r.toTableId,
    label: r.relationshipType,
  }));

  return { nodes, edges, raw };
}
