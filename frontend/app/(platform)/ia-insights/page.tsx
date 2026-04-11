import { redirect } from "next/navigation";

export default function LegacyInsightsRedirect() {
  redirect("/manager/assistant-ia");
}
