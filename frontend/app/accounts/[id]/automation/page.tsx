import { AppShell } from "@/components/console/layout";
import { AutomationPlanPage } from "@/components/console/automation-plan";

export default async function AccountAutomationPlanRoute({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <AppShell>
      <AutomationPlanPage accountId={id} />
    </AppShell>
  );
}
