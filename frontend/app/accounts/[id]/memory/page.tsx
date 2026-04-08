import { AppShell } from "@/components/console/layout";
import { AccountMemoryPage } from "@/components/console/account-memory";

export default async function AccountMemoryRoute({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <AppShell>
      <AccountMemoryPage accountId={id} />
    </AppShell>
  );
}
