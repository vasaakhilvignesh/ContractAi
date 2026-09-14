/**
 * ContractIQ — Frontend API Client
 * 
 * Centralized HTTP client communicating with FastAPI backend:
 * - Automatically injects JWT Bearer authorization headers
 * - Standardized error formatting (401, 403, 404, 422, 500)
 * - Session expiration notification
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export class ApiError extends Error {
  public status: number;
  public data: any;

  constructor(message: string, status: number, data?: any) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

const TOKEN_KEY = "contractiq_access_token";

export const tokenStorage = {
  get: (): string | null => {
    try {
      return localStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },
  set: (token: string): void => {
    try {
      localStorage.setItem(TOKEN_KEY, token);
    } catch {}
  },
  clear: (): void => {
    try {
      localStorage.removeItem(TOKEN_KEY);
    } catch {}
  },
};

export async function apiRequest<T = any>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = endpoint.startsWith("http")
    ? endpoint
    : `${API_BASE_URL}${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`;

  const headers = new Headers(options.headers || {});

  // Add Authorization header if token exists and not already provided
  const token = tokenStorage.get();
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  // Set Content-Type: application/json if body is plain object and not FormData
  if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  try {
    const response = await fetch(url, {
      ...options,
      headers,
    });

    // 204 No Content
    if (response.status === 204) {
      return undefined as unknown as T;
    }

    let responseData: any;
    const contentType = response.headers.get("content-type");
    if (contentType && contentType.includes("application/json")) {
      responseData = await response.json();
    } else {
      responseData = await response.text();
    }

    if (!response.ok) {
      // If 401 Unauthorized, notify application about expired session
      if (response.status === 401) {
        window.dispatchEvent(new CustomEvent("contractiq:unauthorized"));
      }

      const errorMessage =
        (typeof responseData === "object" && responseData?.detail)
          ? typeof responseData.detail === "string"
            ? responseData.detail
            : JSON.stringify(responseData.detail)
          : response.statusText || `Request failed with status ${response.status}`;

      throw new ApiError(errorMessage, response.status, responseData);
    }

    return responseData as T;
  } catch (err: any) {
    if (err instanceof ApiError) {
      throw err;
    }
    throw new ApiError(
      err?.message || "Network connection failed. Backend may be offline.",
      0
    );
  }
}
