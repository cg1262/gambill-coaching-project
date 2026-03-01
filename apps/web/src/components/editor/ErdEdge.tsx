import { BaseEdge, EdgeLabelRenderer, getBezierPath, type EdgeProps } from "reactflow";

function cardinalityFor(rel: string) {
  const r = rel || "many_to_one";
  return {
    left: r === "many_to_one" || r === "many_to_many" ? "N" : "1",
    right: r === "one_to_many" || r === "many_to_many" ? "N" : "1",
  };
}

export default function ErdEdge(props: EdgeProps) {
  const [path, labelX, labelY] = getBezierPath(props);
  const rel = String(props.label ?? "many_to_one");
  const c = cardinalityFor(rel);

  return (
    <>
      <BaseEdge id={props.id} path={path} style={{ stroke: "#3B82F6", strokeWidth: 2.2 }} markerEnd={props.markerEnd} markerStart={props.markerStart} />
      <EdgeLabelRenderer>
        <div style={{ position: "absolute", transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`, fontSize: 11, background: "#eff6ff", color: "#1e3a8a", padding: "1px 8px", border: "1px solid #bfdbfe", borderRadius: 999, fontWeight: 600 }}>
          {rel}
        </div>
        <div style={{ position: "absolute", transform: `translate(-50%, -50%) translate(${props.sourceX + (props.targetX - props.sourceX) * 0.15}px, ${props.sourceY + (props.targetY - props.sourceY) * 0.15}px)`, fontSize: 11, fontWeight: 700, color: "#0f172a" }}>
          {c.left}
        </div>
        <div style={{ position: "absolute", transform: `translate(-50%, -50%) translate(${props.sourceX + (props.targetX - props.sourceX) * 0.85}px, ${props.sourceY + (props.targetY - props.sourceY) * 0.85}px)`, fontSize: 11, fontWeight: 700, color: "#0f172a" }}>
          {c.right}
        </div>
      </EdgeLabelRenderer>
    </>
  );
}
