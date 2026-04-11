import { redirect } from "next/navigation";

export default function LegacyTransformationsRedirect() {
  redirect("/manager/transformations");
}
