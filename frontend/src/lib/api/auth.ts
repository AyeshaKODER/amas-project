// ---------------------------------------------------------------------------
// Auth service – talks to FastAPI auth endpoints
// ---------------------------------------------------------------------------

import * as http from './http';
import type { LoginResponse, UserProfile } from './types';

/**
 * Log in via FastAPI's OAuth2-compatible token endpoint.
 * FastAPI's `OAuth2PasswordRequestForm` expects form-encoded `username` + `password`.
 */
export async function login(email: string, password: string): Promise<LoginResponse> {
  const data = await http.postForm<LoginResponse>('/auth/login', {
    username: email,
    password,
  });
  http.setToken(data.access_token);
  return data;
}

/**
 * Register a new user account.
 */
export async function register(
  email: string,
  password: string,
  name: string,
): Promise<UserProfile> {
  return http.post<UserProfile>('/auth/register', { email, password, name });
}

/**
 * Fetch the currently authenticated user's profile.
 */
export async function getCurrentUser(): Promise<UserProfile> {
  return http.get<UserProfile>('/auth/me');
}

/**
 * Clear local auth state (token + cached user).
 */
export function logout() {
  http.clearToken();
  localStorage.removeItem('amas_user');
}
