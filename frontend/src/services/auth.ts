import api, { setAuthToken as setApiAuthToken } from "./api";

const TOKEN_KEY = "access_token";

export type AuthUser = {
  id: number;
  email: string;
  name?: string | null;
  is_active?: boolean;
  is_admin?: boolean;
};

export type AuthResponse = {
  access_token: string;
  token_type: string;
  refresh_token?: string;
  expires_in?: number;
  user?: AuthUser;
};

type LoginPayload = {
  email: string;
  password: string;
};

type SignupPayload = {
  email: string;
  password: string;
  name?: string;
};

const extractErrorMessage = (error: any, fallback: string) =>
  error?.response?.data?.detail ||
  error?.response?.data?.message ||
  error?.message ||
  fallback;

export const readStoredToken = (): string | null => localStorage.getItem(TOKEN_KEY);

export const setAuthToken = (token: string | null): void => {
  setApiAuthToken(token);
};

export const login = async (payload: LoginPayload): Promise<AuthResponse> => {
  try {
    const response = await api.post("/api/v1/auth/login", payload);
    const data: AuthResponse = response.data;
    if (data?.access_token) {
      setAuthToken(data.access_token);
    }
    return data;
  } catch (error) {
    throw new Error(extractErrorMessage(error, "Login failed"));
  }
};

export const signup = async (payload: SignupPayload): Promise<AuthResponse> => {
  try {
    const response = await api.post("/api/v1/auth/register", payload);
    const data: AuthResponse = response.data;
    if (data?.access_token) {
      setAuthToken(data.access_token);
    }
    return data;
  } catch (error) {
    throw new Error(extractErrorMessage(error, "Signup failed"));
  }
};

export const logout = async (): Promise<void> => {
  setAuthToken(null);
};

export const getCurrentUser = async (): Promise<AuthUser | null> => {
  const token = readStoredToken();
  if (!token) {
    return null;
  }

  setAuthToken(token);
  try {
    const response = await api.get("/api/v1/auth/me");
    return response.data ?? null;
  } catch (error) {
    setAuthToken(null);
    return null;
  }
};

if (readStoredToken()) {
  setAuthToken(readStoredToken());
}

export default { login, signup, logout, getCurrentUser, setAuthToken, readStoredToken };
