# UI Gap Assessment (Current)

## Fixed in latest pass
- Inline field rename on double-click table node.
- FK constraint visibility + toggle.
- Edge rendering restored (handles + ERD edge type).
- Top menu bar scaffold for File/Insert/Connections/Run/View.
- Payload mapping fix to avoid `/impact/deterministic` 422 from camelCase mismatch.

## Remaining high-priority gaps
1. True crow's-foot endpoint glyphs (currently 1/N + marker approximation).
2. Better visual hierarchy/spacing/typography for enterprise polish.
3. Full connector/import dialogs (currently placeholders).
4. Persisted save/open project model (currently JSON export/import only).
5. Rule feedback UX (group by table, click to focus offending object).
6. Toast notifications and operation timelines.
7. Undo/redo and keyboard shortcuts.
8. Dark mode parity with brand tokens.

## Next recommended sprint
- Implement custom edge SVG with proper crow's foot symbols.
- Add command palette + keyboard shortcuts.
- Add modal-based connection manager with secret references.
- Add project save metadata panel (name/version/owner/environment).
