import { jsonOptions, request } from "./http";

export function getHealth() {
  return request("/health");
}

export function listWorkers() {
  return request("/workers");
}

export function refreshSlavers() {
  return request("/slavers?refresh=true");
}

export function listSlavers() {
  return request("/slavers");
}

export function registerSlaver(payload) {
  return request("/slavers", jsonOptions("POST", payload));
}

export function createBrowserEnvironment(payload) {
  return request("/slavers/start", jsonOptions("POST", payload));
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
