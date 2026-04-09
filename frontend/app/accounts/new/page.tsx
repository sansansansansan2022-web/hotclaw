import { AppShell } from "@/components/console/layout";
import { AccountOnboardingWizard } from "@/components/console/account-onboarding-wizard";

export default function NewAccountRoute() {
  return (
    <AppShell>
      <AccountOnboardingWizard />
    </AppShell>
  );
}
