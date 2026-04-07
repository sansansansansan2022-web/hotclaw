import { AppShell } from "@/components/console/layout";
import { TaskDetailPage } from "@/components/console/task-detail";

export default async function TaskDetailRoute({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <AppShell>
      <TaskDetailPage taskId={id} />
    </AppShell>
  );
}
