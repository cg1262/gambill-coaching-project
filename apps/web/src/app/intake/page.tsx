import { Suspense } from "react";
import CoachingProjectWorkbench from "../../components/coaching/CoachingProjectWorkbench";

export default function IntakePage() {
  return (
    <Suspense fallback={<div style={{ padding: 16 }}>Loading intake workbench…</div>}>
      <CoachingProjectWorkbench mode="intake" />
    </Suspense>
  );
}
