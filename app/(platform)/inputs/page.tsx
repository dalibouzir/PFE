import { redirect } from "next/navigation";

export default function LegacyInputsRedirect() {
  redirect("/manager/inputs");
}
