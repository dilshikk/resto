import { apiClient, refreshClient } from "./client.ts";

export type LoginRequest = { email: string; password: string };

/**
 * Shape of the access-token-only response now returned by the server.
 * The refresh token is delivered as an httpOnly cookie — it never appears
 * in the JSON body.
 */
export type TokenResponse = { access_token: string; token_type: string };

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
 * Exchange a pre-auth token + TOTP code for a real access token.
 * The server sets the refresh token as an httpOnly cookie.
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

/**
 * Silently exchange the httpOnly refresh-token cookie for a new access token.
 * Called on page load by AuthProvider to restore the session without the user
 * having to log in again.
 */
export async function silentRefresh(): Promise<TokenResponse> {
  const res = await refreshClient.post<TokenResponse>("/auth/refresh");
  return res.data;
}

export async function logout(): Promise<void> {
  // POST /auth/logout revokes the access token (via Authorization header)
  // and the refresh token (from the httpOnly cookie) server-side, then
  // clears the cookie.  No body is required for the refresh token anymore.
  await apiClient.post("/auth/logout");
}
