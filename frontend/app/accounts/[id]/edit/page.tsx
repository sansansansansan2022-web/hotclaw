import { AppShell } from "@/components/console/layout";
import { AccountFormPage } from "@/components/console/account-form";

export default async function EditAccountRoute({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <AppShell>
      <AccountFormPage accountId={id} />
    </AppShell>
  );
}
