import { TaskHistoryPage } from "@/components/console/task-history";

export default async function TaskHistoryRoute({
  searchParams,
}: {
  searchParams: Promise<{ account_id?: string }>;
}) {
  const params = await searchParams;
  return <TaskHistoryPage initialAccountId={params.account_id} />;
}
