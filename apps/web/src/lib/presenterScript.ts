export type DemoStep = {
  id: string;
  title: string;
  prompt: string;
};

export const DATATUNE_STEPS: DemoStep[] = [
  {
    id: "intro",
    title: "Intro",
    prompt:
      "Set context: This IDE bridges governance standards with physical warehouse design, using deterministic + probabilistic validation.",
  },
  {
    id: "load",
    title: "Load telecom schema",
    prompt:
      "Load telecom demo graph and point out entities and relationships on the visual canvas.",
  },
  {
    id: "edit",
    title: "Edit model",
    prompt:
      "Modify a node/column in the side panel editor to show how quickly a model change can be proposed.",
  },
  {
    id: "det-validate",
    title: "Deterministic validation",
    prompt:
      "Run deterministic validation and explain trusted checks (PKs, naming, dictionaries, metadata).",
  },
  {
    id: "det-impact",
    title: "Deterministic impact",
    prompt:
      "Run deterministic impact and highlight 100% confidence lineage-driven dependencies.",
  },
  {
    id: "prob",
    title: "Probabilistic + confidence gating",
    prompt:
      "Run probabilistic impact and explain confidence thresholds + color bands (red/yellow/green).",
  },
  {
    id: "close",
    title: "Close",
    prompt:
      "Reinforce value: safer, faster schema iteration with policy-aligned governance and transparent confidence.",
  },
];
