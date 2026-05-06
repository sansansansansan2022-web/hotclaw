import { redirect } from "next/navigation";

export default function LegacyHistoryRoute() {
  redirect("/tasks/history");
}
