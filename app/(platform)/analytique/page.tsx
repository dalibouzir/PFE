import { redirect } from "next/navigation";

export default function LegacyAnalyticsRedirect() {
  redirect("/manager/lots?tab=analytics");
}
