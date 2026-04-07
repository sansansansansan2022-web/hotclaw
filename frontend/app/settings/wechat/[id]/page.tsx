import { AppShell } from "@/components/console/layout";
import { WeChatConfigPage } from "@/components/console/wechat-config";

export default async function WeChatConfigRoute({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <AppShell>
      <WeChatConfigPage accountId={id} />
    </AppShell>
  );
}
