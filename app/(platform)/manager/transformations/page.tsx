import { redirect } from "next/navigation";

export default function ManagerTransformationsRedirect() {
  redirect("/manager/lots?tab=process");
}
