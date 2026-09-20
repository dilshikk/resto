import { apiClient } from "./client.ts";

export type LoginRequest = { email: string; password: string };
export type TokenResponse = { access_token: string; refresh_token: string; token_type: string };

/**
 * Discriminated union returned by POST /auth/login.
 *
 * When 2FA is enabled the server issues a short-lived pre_auth_token instead
 * of real tokens.  The caller must exchange it via verify2fa() before the
 * user is considered authenticated.
 */
export type LoginApiResponse =
  | { requires_2fa: true; pre_auth_token: string }
  | (TokenResponse & { requires_2fa?: false });

export async function login(data: LoginRequest): Promise<LoginApiResponse> {
  const form = new URLSearchParams();
  form.append("username", data.email);
  form.append("password", data.password);
  const res = await apiClient.post<LoginApiResponse>("/auth/login", form, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
  return res.data;
}

/**
 * Exchange a pre-auth token + TOTP code for a real access/refresh token pair.
 * Called only when POST /auth/login returned requires_2fa=true.
 */
export async function verify2fa(
  pre_auth_token: string,
  code: string,
): Promise<TokenResponse> {
  const res = await apiClient.post<TokenResponse>("/auth/2fa/verify", {
    pre_auth_token,
    code,
  });
  return res.data;
}

export async function refreshToken(token: string): Promise<TokenResponse> {
  const res = await apiClient.post<TokenResponse>("/auth/refresh", { refresh_token: token });
  return res.data;
}

export async function logout(): Promise<void> {
  // Send the refresh token too so the backend can revoke it, not just the
  // access token — otherwise it could keep minting new access tokens after
  // this "logged out" session ends.
  const refresh_token = localStorage.getItem("refresh_token") ?? undefined;
  await apiClient.post("/auth/logout", { refresh_token });
}
