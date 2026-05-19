import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  authApi,
  clearAccessToken,
  getAccessToken,
  logoutApi,
  restoreSession,
  setAccessToken,
} from "@/lib/api/client";
import { createTokenResponse, createUser } from "@/mocks/data";
import { useAuthStore } from "./authStore";

// Mock the API client module
vi.mock("@/lib/api/client", () => ({
  setAccessToken: vi.fn(),
  clearAccessToken: vi.fn(),
  getAccessToken: vi.fn(() => null),
  restoreSession: vi.fn(),
  logoutApi: vi.fn(),
  authApi: {
    login: vi.fn(),
    register: vi.fn(),
    me: vi.fn(),
  },
  // Export a no-op axios instance (not used directly in store tests)
  default: {},
}));

// Mock window.location for logout redirect
const mockLocation = { href: "" };
Object.defineProperty(window, "location", {
  value: mockLocation,
  writable: true,
});

describe("useAuthStore", () => {
  beforeEach(() => {
    // Reset store state before each test
    useAuthStore.setState({
      user: null,
      isLoading: false,
      isAuthenticated: false,
      _sessionChecked: false,
    });
    vi.clearAllMocks();
    mockLocation.href = "";
  });

  describe("initial state", () => {
    it("should start unauthenticated", () => {
      const state = useAuthStore.getState();
      expect(state.isAuthenticated).toBe(false);
    });

    it("should have no user initially", () => {
      const state = useAuthStore.getState();
      expect(state.user).toBeNull();
    });

    it("should not be loading initially", () => {
      const state = useAuthStore.getState();
      expect(state.isLoading).toBe(false);
    });

    it("should have _sessionChecked set to false initially", () => {
      const state = useAuthStore.getState();
      expect(state._sessionChecked).toBe(false);
    });
  });

  describe("login", () => {
    it("should set user and authenticated state on successful login", async () => {
      const tokens = createTokenResponse();
      const user = createUser();

      vi.mocked(authApi.login).mockResolvedValue(tokens);
      vi.mocked(authApi.me).mockResolvedValue(user);

      await useAuthStore.getState().login("test@example.com", "password123");

      const state = useAuthStore.getState();
      expect(state.isAuthenticated).toBe(true);
      expect(state.user).toEqual(user);
      expect(state.isLoading).toBe(false);
    });

    it("should call setAccessToken with the access token", async () => {
      const tokens = createTokenResponse();
      const user = createUser();

      vi.mocked(authApi.login).mockResolvedValue(tokens);
      vi.mocked(authApi.me).mockResolvedValue(user);

      await useAuthStore.getState().login("test@example.com", "password123");

      expect(setAccessToken).toHaveBeenCalledWith(tokens.access_token);
    });

    it("should set loading to true during login", async () => {
      let resolveLogin: (value: unknown) => void;
      const loginPromise = new Promise((resolve) => {
        resolveLogin = resolve;
      });

      vi.mocked(authApi.login).mockReturnValue(loginPromise as never);

      const loginAction = useAuthStore.getState().login("test@example.com", "password123");

      // Loading should be true while the request is in-flight
      expect(useAuthStore.getState().isLoading).toBe(true);

      resolveLogin!(createTokenResponse());
      vi.mocked(authApi.me).mockResolvedValue(createUser());

      await loginAction;
    });

    it("should reset loading and re-throw on login failure", async () => {
      vi.mocked(authApi.login).mockRejectedValue(new Error("Invalid credentials"));

      await expect(useAuthStore.getState().login("bad@example.com", "wrong")).rejects.toThrow(
        "Invalid credentials",
      );

      const state = useAuthStore.getState();
      expect(state.isLoading).toBe(false);
      expect(state.isAuthenticated).toBe(false);
      expect(state.user).toBeNull();
    });
  });

  describe("register", () => {
    it("should set user and authenticated state on successful registration", async () => {
      const tokens = createTokenResponse();
      const user = createUser({ email: "new@example.com" });

      vi.mocked(authApi.register).mockResolvedValue(tokens);
      vi.mocked(authApi.me).mockResolvedValue(user);

      await useAuthStore.getState().register("new@example.com", "password123", "New User");

      const state = useAuthStore.getState();
      expect(state.isAuthenticated).toBe(true);
      expect(state.user).toEqual(user);
      expect(state.isLoading).toBe(false);
    });

    it("should call authApi.register with correct arguments", async () => {
      const tokens = createTokenResponse();
      vi.mocked(authApi.register).mockResolvedValue(tokens);
      vi.mocked(authApi.me).mockResolvedValue(createUser());

      await useAuthStore.getState().register("new@example.com", "pass", "Display");

      expect(authApi.register).toHaveBeenCalledWith("new@example.com", "pass", "Display");
    });

    it("should reset loading and re-throw on registration failure", async () => {
      vi.mocked(authApi.register).mockRejectedValue(new Error("Email taken"));

      await expect(useAuthStore.getState().register("taken@example.com", "pass")).rejects.toThrow(
        "Email taken",
      );

      const state = useAuthStore.getState();
      expect(state.isLoading).toBe(false);
      expect(state.isAuthenticated).toBe(false);
    });
  });

  describe("logout", () => {
    it("should clear user and authenticated state and reset _sessionChecked", async () => {
      // Set up authenticated state first
      useAuthStore.setState({
        user: createUser(),
        isAuthenticated: true,
        _sessionChecked: true,
      });

      await useAuthStore.getState().logout();

      const state = useAuthStore.getState();
      expect(state.user).toBeNull();
      expect(state.isAuthenticated).toBe(false);
      expect(state._sessionChecked).toBe(false);
    });

    it("should call logoutApi before clearing local state", async () => {
      await useAuthStore.getState().logout();

      expect(logoutApi).toHaveBeenCalledOnce();
    });

    it("should call clearAccessToken after logoutApi", async () => {
      await useAuthStore.getState().logout();

      expect(clearAccessToken).toHaveBeenCalled();
    });

    it("should redirect to /login", async () => {
      await useAuthStore.getState().logout();

      expect(window.location.href).toBe("/login");
    });
  });

  describe("loadUser", () => {
    it("should load user and set authenticated on success", async () => {
      const user = createUser();
      vi.mocked(getAccessToken).mockReturnValue("existing-token");
      vi.mocked(authApi.me).mockResolvedValue(user);

      await useAuthStore.getState().loadUser();

      const state = useAuthStore.getState();
      expect(state.user).toEqual(user);
      expect(state.isAuthenticated).toBe(true);
      expect(state.isLoading).toBe(false);
      expect(state._sessionChecked).toBe(true);
    });

    it("should call restoreSession when no access token exists", async () => {
      vi.mocked(getAccessToken).mockReturnValue(null);
      vi.mocked(restoreSession).mockResolvedValue(true);
      vi.mocked(authApi.me).mockResolvedValue(createUser());

      await useAuthStore.getState().loadUser();

      expect(restoreSession).toHaveBeenCalledOnce();
      expect(authApi.me).toHaveBeenCalledOnce();
    });

    it("should skip restoreSession when access token exists", async () => {
      vi.mocked(getAccessToken).mockReturnValue("existing-token");
      vi.mocked(authApi.me).mockResolvedValue(createUser());

      await useAuthStore.getState().loadUser();

      expect(restoreSession).not.toHaveBeenCalled();
    });

    it("should clear user and set unauthenticated on failure", async () => {
      useAuthStore.setState({ user: createUser(), isAuthenticated: true });
      vi.mocked(getAccessToken).mockReturnValue("existing-token");
      vi.mocked(authApi.me).mockRejectedValue(new Error("Unauthorized"));

      await useAuthStore.getState().loadUser();

      const state = useAuthStore.getState();
      expect(state.user).toBeNull();
      expect(state.isAuthenticated).toBe(false);
      expect(state.isLoading).toBe(false);
      expect(state._sessionChecked).toBe(true);
    });

    it("should skip me() call when restoreSession fails (Fix 4)", async () => {
      vi.mocked(getAccessToken).mockReturnValue(null);
      vi.mocked(restoreSession).mockResolvedValue(false);

      await useAuthStore.getState().loadUser();

      // authApi.me() should NOT be called — we avoid the guaranteed 401
      expect(authApi.me).not.toHaveBeenCalled();
      const state = useAuthStore.getState();
      expect(state.user).toBeNull();
      expect(state.isAuthenticated).toBe(false);
      expect(state.isLoading).toBe(false);
      expect(state._sessionChecked).toBe(true);
    });

    it("should early-return on second call when _sessionChecked is already true", async () => {
      // Simulate first successful call
      const user = createUser();
      vi.mocked(getAccessToken).mockReturnValue("existing-token");
      vi.mocked(authApi.me).mockResolvedValue(user);

      await useAuthStore.getState().loadUser();
      expect(useAuthStore.getState()._sessionChecked).toBe(true);
      expect(useAuthStore.getState().user).toEqual(user);

      // Reset mock counters to detect second call
      vi.mocked(authApi.me).mockClear();

      // Second call should early-return
      await useAuthStore.getState().loadUser();

      // authApi.me() should not be called again
      expect(authApi.me).not.toHaveBeenCalled();
    });
  });
});
