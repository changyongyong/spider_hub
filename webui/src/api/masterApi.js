import { jsonOptions, request } from "./http";

export function login(payload) {
  return request("/auth/login", jsonOptions("POST", payload));
}

export function getCurrentUser() {
  return request("/auth/me");
}

export function logout() {
  return request("/auth/logout", jsonOptions("POST", {}));
}

export function getHealth() {
  return request("/health");
}

export function listWorkers() {
  return request("/slaves/environments");
}

export function refreshSlaves() {
  return request("/slaves?refresh=true");
}

export function listSlaves() {
  return request("/slaves");
}

export function registerSlave(payload) {
  return request("/slaves", jsonOptions("POST", payload));
}

export function createBrowserEnvironment(payload) {
  return request("/slaves/environments", jsonOptions("POST", payload));
}

export function updateBrowserEnvironment(workerId, payload) {
  return request(`/slaves/environments/${encodeURIComponent(workerId)}`, jsonOptions("PATCH", payload));
}

export function startBrowserEnvironment(workerId) {
  return request(`/slaves/environments/${encodeURIComponent(workerId)}/start`, jsonOptions("POST", {}));
}

export function stopBrowserEnvironment(workerId) {
  return request(`/slaves/environments/${encodeURIComponent(workerId)}/stop`, jsonOptions("POST", {}));
}

export function deleteWorker(workerId) {
  return request(`/slaves/environments/${encodeURIComponent(workerId)}`, { method: "DELETE" });
}

export function listJobs() {
  return request("/jobs");
}

export function submitJob(payload) {
  return request("/jobs", jsonOptions("POST", payload));
}

export function fetchUrl(payload) {
  return request("/fetch", jsonOptions("POST", payload));
}
