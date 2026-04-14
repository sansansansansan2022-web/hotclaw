import { AppShell } from "@/components/console/layout";
import { AccountComposeFlowPage } from "@/components/console/account-compose-flow";

export default async function AccountCreateRoute({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <AppShell>
      <AccountComposeFlowPage accountId={id} />
    </AppShell>
  );
}
