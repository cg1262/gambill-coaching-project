import { Handle, Position, type NodeProps } from "reactflow";
import type { EditableNodeData, ColumnDef } from "../../lib/types";

type NodeData = EditableNodeData & {
  inlineEdit?: boolean;
  compact?: boolean;
  onInlineRename?: (idx: number, name: string) => void;
};

export default function TableNode({ data, selected }: NodeProps<NodeData>) {
  const cols: ColumnDef[] = data?.columns ?? [];

  return (
    <div
      style={{
        minWidth: 320,
        maxWidth: 380,
        border: selected ? "2px solid #F59E0B" : "1px solid #cbd5e1",
        borderRadius: 12,
        background: "linear-gradient(180deg, #ffffff 0%, #f8fafc 100%)",
        boxShadow: selected ? "0 10px 24px rgba(15,23,42,0.2)" : "0 6px 16px rgba(15,23,42,0.12)",
        overflow: "hidden",
      }}
    >
      <Handle type="target" position={Position.Left} style={{ background: "#334155", width: 8, height: 8 }} />
      <Handle type="source" position={Position.Right} style={{ background: "#334155", width: 8, height: 8 }} />

      <div style={{ background: "linear-gradient(90deg, #0F172A 0%, #1E293B 55%, #334155 100%)", color: "#fff", padding: "8px 10px", fontWeight: 700 }}>{data?.label ?? "table"}</div>
      <div style={{ padding: "8px 10px", fontSize: 12, color: "#334155", background: "rgba(59,130,246,0.10)", fontWeight: 600 }}>{data?.schema ?? "demo"}</div>

      {data?.compact && !selected ? (
        <div style={{ padding: "8px 10px", fontSize: 12, color: "#334155" }}>
          {cols.length} columns · compact mode
        </div>
      ) : (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "1.4fr .8fr .8fr", gap: 8, padding: "0 10px 6px", fontSize: 11, color: "#334155", fontWeight: 600 }}>
            <div>Field</div><div>Type</div><div>Constraints</div>
          </div>

          <div style={{ maxHeight: 140, overflowY: "auto", padding: "0 10px 10px" }}>
            {cols.map((c, i) => (
              <div key={`r-${i}`} style={{ display: "grid", gridTemplateColumns: "1.4fr .8fr .8fr", gap: 8, alignItems: "center", fontSize: 12, color: "#0f172a", padding: "3px 0", borderTop: "1px solid #e2e8f0" }}>
                {data?.inlineEdit ? (
                  <input
                    value={c.name}
                    onChange={(e) => data.onInlineRename?.(i, e.target.value)}
                    style={{ border: "1px solid #e2e8f0", borderRadius: 4, padding: "2px 4px", fontSize: 12 }}
                  />
                ) : (
                  <div>{c.name}</div>
                )}
                <div style={{ color: "#334155" }}>{c.dataType}</div>
                <div style={{ color: "#475569" }}>
                  {c.isPrimaryKey ? "PK" : ""}{c.isPrimaryKey && c.isForeignKey ? ", " : ""}{c.isForeignKey ? "FK" : ""}{!c.isPrimaryKey && !c.isForeignKey ? "-" : ""}
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
