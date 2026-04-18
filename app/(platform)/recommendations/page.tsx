import { redirect } from "next/navigation";

export default function LegacyRecommendationsRedirect() {
  redirect("/manager/lots?tab=recommendations");
}
