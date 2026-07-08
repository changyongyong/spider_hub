const defaultHeaders = {
  "Content-Type": "application/json"
};

export const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");
export const apiProxyTarget = import.meta.env.VITE_API_PROXY_TARGET || "";
const authStorageKey = "spider_master_auth";

export async function request(path, options = {}) {
  const response = await fetch(requestUrl(path), {
    ...options,
    headers: requestHeaders(options.headers)
  });

  if (!response.ok) {
    const message = await readError(response);
    if (response.status === 401) {
      clearAuthSession();
      window.dispatchEvent(new CustomEvent("spider-auth-expired"));
    }
    throw new Error(message);
  }

  if (response.status === 204) {
    return null;
  }

  return response.json();
}

function requestHeaders(headers = {}) {
  const result = { ...defaultHeaders, ...headers };
  const session = getAuthSession();
  if (session?.access_token) {
    result.Authorization = `Bearer ${session.access_token}`;
  }
  return result;
}

function requestUrl(path) {
  if (!apiBaseUrl) {
    return path;
  }
  return `${apiBaseUrl}${path}`;
}

async function readError(response) {
  const text = await response.text();
  if (!text) {
    return `${response.status} ${response.statusText}`;
  }

  try {
    const payload = JSON.parse(text);
    return payload.detail || text;
  } catch {
    return text;
  }
}

export function jsonOptions(method, body) {
  return {
    method,
    body: JSON.stringify(body)
  };
}

export function getAuthSession() {
  const text = window.localStorage.getItem(authStorageKey);
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

export function setAuthSession(session) {
  window.localStorage.setItem(authStorageKey, JSON.stringify(session));
}

export function clearAuthSession() {
  window.localStorage.removeItem(authStorageKey);
}
