import { AppShell } from "@/components/console/layout";
import { DraftDetailPage } from "@/components/console/draft-detail";

export default async function DraftDetailRoute({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <AppShell>
      <DraftDetailPage draftId={id} />
    </AppShell>
  );
}
