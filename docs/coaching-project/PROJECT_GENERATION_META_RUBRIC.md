# Gambill Data Project Generation Standards (Meta-Rubric)

This rubric evaluates the quality of the generated Project Charter/SOW (not student implementation output quality).

## Phase 1: Structure and Business Context

1. Structural Compliance
- Metric: Output adheres to required SOW format.
- Standard: Includes project header, executive summary, technical architecture (ingestion/processing/storage/serving), implementation plan, milestone tracker, and ROI dashboard requirements.

2. Client Contextual Realism
- Metric: Fictitious scenario is industry-accurate and pain-point specific.
- Standard: Should read like a real consulting engagement, not a generic tutorial setup.

3. Golden Thread (Business-Technical Mapping)
- Metric: Technical decisions map explicitly to business outcomes.
- Standard: Milestones and architecture language connect directly to KPI/ROI intent.

## Phase 2: Technical Architecture

4. Architectural Cohesion
- Metric: Stack is cohesive and enterprise-realistic.
- Standard: Avoids mismatched Franken-stack designs and shows ecosystem consistency.

5. Ingestion Complexity
- Metric: Source patterns require realistic ingestion handling.
- Standard: Includes patterns like incremental polling, CDC, late-arriving data, pagination, or similar production concerns.

6. Medallion Layer Precision
- Metric: Bronze/Silver/Gold responsibilities are explicit.
- Standard: Gold requirements include BI-oriented dimensional modeling expectations where appropriate.

7. Enterprise Resiliency Mandates
- Metric: SOW requires DQ, idempotency, and observability.
- Standard: Includes audit/logging intent and bad-record handling expectations.

## Phase 3: Execution and Deliverables

8. ROI-Driven Servicing Requirements
- Metric: Dashboard requirements focus on actionable insights.
- Standard: Business questions and visuals are decision-oriented, not table dumps.

9. Milestone Estimation and Definition of Done
- Metric: Milestones are realistic and include clear completion criteria.
- Standard: Engineering phases and DoD expectations are explicit.

10. Persona Calibration
- Metric: Difficulty level matches candidate goals/level.
- Standard: Senior paths require advanced production concepts; junior paths emphasize core engineering fundamentals.
