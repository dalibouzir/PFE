import { redirect } from "next/navigation";

export default function ManagerAnalyticsRedirect() {
  redirect("/manager/lots?tab=analytics");
}
