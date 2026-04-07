import { AppShell } from "@/components/console/layout";
import { WeChatConfigPage } from "@/components/console/wechat-config";

export default function WeChatConfigIndexRoute() {
  return (
    <AppShell>
      <WeChatConfigPage />
    </AppShell>
  );
}
