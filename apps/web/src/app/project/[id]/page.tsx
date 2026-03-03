import CoachingProjectWorkbench from "../../../components/coaching/CoachingProjectWorkbench";

export default function ProjectPage({ params }: { params: { id: string } }) {
  return <CoachingProjectWorkbench mode="project" projectId={params.id} />;
}
