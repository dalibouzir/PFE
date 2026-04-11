import { redirect } from "next/navigation";

export default function LegacyLotsRedirect() {
  redirect("/manager/lots");
}
