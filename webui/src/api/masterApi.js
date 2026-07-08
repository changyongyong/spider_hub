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
  return request("/workers");
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
  return request("/slaves/start", jsonOptions("POST", payload));
}

export function deleteWorker(workerId) {
  return request(`/workers/${encodeURIComponent(workerId)}`, { method: "DELETE" });
}

export function listJobs() {
  return request("/jobs");
}

export function submitJob(payload) {
  return request("/jobs", jsonOptions("POST", payload));
}
