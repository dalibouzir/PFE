import { redirect } from "next/navigation";

export default function LegacyMembersRedirect() {
  redirect("/manager/membres");
}
