export type DataType = "string" | "int" | "bigint" | "decimal" | "boolean" | "date" | "timestamp" | "json" | "array" | "struct";

export interface ColumnDef {
  name: string;
  dataType: DataType;
  nullable: boolean;
  isPrimaryKey?: boolean;
  isForeignKey?: boolean;
}

export interface CanvasTableNode {
  id: string;
  schema: string;
  table: string;
  columns: ColumnDef[];
  source: "mock" | "unity_catalog";
  position: { x: number; y: number };
}

export interface CanvasRelationshipJoin {
  fromColumn: string;
  toColumn: string;
}

export interface CanvasRelationship {
  id: string;
  fromTableId: string;
  toTableId: string;
  fromColumn: string;
  toColumn: string;
  joinColumns?: CanvasRelationshipJoin[];
  relationshipType: "one_to_one" | "one_to_many" | "many_to_one" | "many_to_many";
}

export interface CanvasAST {
  version: "1.0";
  workspaceId: string;
  tables: CanvasTableNode[];
  relationships: CanvasRelationship[];
  modifiedTableIds?: string[];
}

export interface EditableNodeData {
  label: string;
  schema?: string;
  columns?: ColumnDef[];
}
