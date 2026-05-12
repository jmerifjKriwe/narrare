import { redirect } from "next/navigation";

// Root page: redirect to dashboard (auth middleware handles unauthenticated users)
export default function RootPage() {
  redirect("/dashboard");
}
