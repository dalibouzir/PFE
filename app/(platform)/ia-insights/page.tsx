import { redirect } from "next/navigation";

export default function LegacyInsightsRedirect() {
  redirect("/manager/lots?tab=recommendations");
}
