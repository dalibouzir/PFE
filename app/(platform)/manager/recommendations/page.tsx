import { redirect } from "next/navigation";

export default function ManagerRecommendationsRedirect() {
  redirect("/manager/lots?tab=recommendations");
}
