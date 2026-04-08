import { AppShell } from "@/components/console/layout";
import { AccountStyleProfilePage } from "@/components/console/style-profile";

export default async function AccountStyleProfileRoute({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <AppShell>
      <AccountStyleProfilePage accountId={id} />
    </AppShell>
  );
}
