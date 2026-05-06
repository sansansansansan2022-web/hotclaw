import { AppShell } from "@/components/console/layout";
import { SettingsPage } from "@/components/console/settings-overview";

export default function SettingsRoute() {
  return (
    <AppShell>
      <SettingsPage />
    </AppShell>
  );
}
