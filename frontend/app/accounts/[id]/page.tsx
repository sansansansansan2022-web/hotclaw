import { AppShell } from "@/components/console/layout";
import { AccountDetailPage } from "@/components/console/account-detail";

export default async function AccountDetailRoute({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <AppShell>
      <AccountDetailPage accountId={id} />
    </AppShell>
  );
}
