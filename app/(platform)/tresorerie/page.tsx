import { redirect } from "next/navigation";

export default function LegacyTreasuryRedirect() {
  redirect("/manager/tresorerie");
}
