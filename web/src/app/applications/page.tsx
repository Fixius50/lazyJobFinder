import { redirect } from "next/navigation";

export default function ApplicationsRedirect() {
  redirect("/?tab=applications");
}
