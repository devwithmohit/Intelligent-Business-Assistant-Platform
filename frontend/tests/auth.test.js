import { beforeEach, describe, expect, it, vi } from "vitest";

const postMock = vi.fn();
const getMock = vi.fn();
const setApiAuthTokenMock = vi.fn();

vi.mock("../src/services/api", () => ({
  default: {
    post: postMock,
    get: getMock,
    defaults: { headers: { common: {} } },
  },
  setAuthToken: setApiAuthTokenMock,
}));

import { getCurrentUser, login, readStoredToken } from "../src/services/auth";

describe("auth service", () => {
  beforeEach(() => {
    localStorage.clear();
    postMock.mockReset();
    getMock.mockReset();
    setApiAuthTokenMock.mockReset();
  });

  it("returns null when there is no stored token", async () => {
    const currentUser = await getCurrentUser();
    expect(currentUser).toBeNull();
  });

  it("stores the access token after login", async () => {
    postMock.mockResolvedValue({
      data: {
        access_token: "token-123",
        token_type: "bearer",
        user: { id: 1, email: "user@example.com" },
      },
    });

    const response = await login({
      email: "user@example.com",
      password: "Password123!",
    });

    expect(response.access_token).toBe("token-123");
    expect(setApiAuthTokenMock).toHaveBeenCalledWith("token-123");
  });

  it("reads tokens from local storage", () => {
    localStorage.setItem("access_token", "stored-token");
    expect(readStoredToken()).toBe("stored-token");
  });
});
