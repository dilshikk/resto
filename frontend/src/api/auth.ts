import { apiClient } from "./client.ts";

export type LoginRequest = { email: string; password: string };
export type TokenResponse = { access_token: string; refresh_token: string; token_type: string };

export async function login(data: LoginRequest): Promise<TokenResponse> {
  const form = new URLSearchParams();
  form.append("username", data.email);
  form.append("password", data.password);
  const res = await apiClient.post<TokenResponse>("/auth/login", form, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
  return res.data;
}

export async function refreshToken(token: string): Promise<TokenResponse> {
  const res = await apiClient.post<TokenResponse>("/auth/refresh", { refresh_token: token });
  return res.data;
}

export async function logout(): Promise<void> {
  await apiClient.post("/auth/logout");
}
