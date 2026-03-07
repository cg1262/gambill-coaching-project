import { Suspense } from "react";
import CoachingProjectWorkbench from "../../components/coaching/CoachingProjectWorkbench";

export default function ReviewPage() {
  return (
    <Suspense fallback={<div style={{ padding: 16 }}>Loading review workbench…</div>}>
      <CoachingProjectWorkbench mode="review" />
    </Suspense>
  );
}
