import { redirect } from "next/navigation";

export default function LegacyFarmerAdvancesRedirect() {
  redirect("/manager/avances-producteurs");
}
