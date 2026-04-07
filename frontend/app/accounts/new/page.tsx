import { AppShell } from "@/components/console/layout";
import { AccountFormPage } from "@/components/console/account-form";

export default function NewAccountRoute() {
  return (
    <AppShell>
      <AccountFormPage />
    </AppShell>
  );
}
