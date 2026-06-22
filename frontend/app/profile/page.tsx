import { LoginGate } from "@/components/login-gate";
import { api, type Profile } from "@/lib/api";
import { ProfileHub } from "./profile-hub";

export const dynamic = "force-dynamic";

export default async function ProfilePage() {
  let profile: Profile | null = null;
  try {
    profile = await api.profile.get();
  } catch {}

  return (
    <LoginGate>
      <ProfileHub initial={profile} />
    </LoginGate>
  );
}
