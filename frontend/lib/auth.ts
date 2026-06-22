import type { NextAuthOptions } from "next-auth";
import GoogleProvider from "next-auth/providers/google";

const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";

// Tauscht den frischen Google-id_token EINMALIG gegen ein langlebiges Backend-Token
// (Fernet, ~30 Tage). Damit hängt die API-Auth nicht mehr am 1h-Ablauf des Google-Tokens.
async function exchangeForBackendToken(idToken: string): Promise<string | undefined> {
  try {
    const res = await fetch(`${BACKEND}/auth/session`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id_token: idToken })
    });
    if (!res.ok) return undefined;
    const data = await res.json();
    return data.token as string;
  } catch {
    return undefined;
  }
}

export const authOptions: NextAuthOptions = {
  providers: [
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID ?? "",
      clientSecret: process.env.GOOGLE_CLIENT_SECRET ?? ""
    })
  ],
  session: { strategy: "jwt" },
  callbacks: {
    async jwt({ token, account }) {
      // Beim Login: Google-id_token gegen das langlebige Backend-Token tauschen.
      if (account?.id_token) {
        token.googleIdToken = account.id_token;
        const backend = await exchangeForBackendToken(account.id_token);
        if (backend) token.backendToken = backend;
      }
      return token;
    },
    async session({ session, token }) {
      // Bevorzugt das Backend-Token; Fallback auf den (frischen) Google-Token beim Login.
      (session as { idToken?: string }).idToken =
        (token.backendToken as string | undefined) ?? (token.googleIdToken as string | undefined);
      return session;
    }
  }
};
