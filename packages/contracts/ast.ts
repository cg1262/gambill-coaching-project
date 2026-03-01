export type UUID = string;

export interface Position {
  x: number;
  y: number;
}

export type DataType =
  | "string"
  | "int"
  | "bigint"
  | "decimal"
  | "boolean"
  | "date"
  | "timestamp"
  | "json"
  | "array"
  | "struct";

export interface ColumnDef {
  name: string;
  dataType: DataType;
  nullable: boolean;
  isPrimaryKey?: boolean;
  description?: string;
  tags?: string[];
}

export interface TableNode {
  id: UUID;
  catalog?: string;
  schema: string;
  table: string;
  description?: string;
  columns: ColumnDef[];
  position: Position;
  source: "mock" | "unity_catalog";
}

export type RelationshipType = "one_to_one" | "one_to_many" | "many_to_one" | "many_to_many";

export interface RelationshipEdge {
  id: UUID;
  fromTableId: UUID;
  toTableId: UUID;
  fromColumn: string;
  toColumn: string;
  relationshipType: RelationshipType;
}

export interface CanvasAST {
  version: "1.0";
  workspaceId: UUID;
  tables: TableNode[];
  relationships: RelationshipEdge[];
  modifiedTableIds?: UUID[];
}

export type Severity = "HIGH" | "MED" | "LOW";

export interface Violation {
  code: string;
  severity: Severity;
  message: string;
  tableId?: UUID;
  columnName?: string;
  source: "deterministic" | "probabilistic";
  confidence?: number; // required for probabilistic findings
}

export interface ValidationResult {
  violations: Violation[];
  checkedAt: string;
}

export interface Dependency {
  objectName: string;
  dependencyType: "table" | "view" | "pipeline" | "code_ref";
  source: "deterministic" | "probabilistic";
  confidence: number;
  color: "red" | "yellow" | "green";
}

export interface ImpactResult {
  dependencies: Dependency[];
  checkedAt: string;
}
