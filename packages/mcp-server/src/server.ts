// Placeholder MCP server wrappers for FastAPI endpoints.
// Phase 1 scaffold: can be wired to actual MCP SDK in next pass.

export type ToolSpec = {
  name: string;
  description: string;
  endpoint: string;
};

export const TOOLS: ToolSpec[] = [
  { name: "validate_deterministic", description: "Run deterministic schema validation", endpoint: "/validate/deterministic" },
  { name: "validate_probabilistic", description: "Run probabilistic schema validation", endpoint: "/validate/probabilistic" },
  { name: "impact_deterministic", description: "Run deterministic impact analysis", endpoint: "/impact/deterministic" },
  { name: "impact_probabilistic", description: "Run probabilistic impact analysis", endpoint: "/impact/probabilistic" },
];
