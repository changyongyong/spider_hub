import { computed, onBeforeUnmount, ref } from "vue";
import {
  deleteWorker,
  getHealth,
  listJobs,
  listSlaves,
  listWorkers,
  refreshSlaves,
  registerSlave,
  createBrowserEnvironment,
  submitJob
} from "../api/masterApi";
import { countByStatus } from "../domain/dashboard";

export function useDashboard() {
  const health = ref({ ok: false, workers: 0 });
  const workers = ref([]);
  const slaves = ref([]);
  const jobs = ref([]);
  const latestResult = ref({});
  const loading = ref(false);
  const message = ref("");
  const error = ref("");
  const lastUpdatedAt = ref(null);
  let timer = null;

  const jobCounts = computed(() => countByStatus(jobs.value));
  const remoteWorkers = computed(() => workers.value.filter((worker) => worker.kind === "remote"));

  async function refresh(options = {}) {
    const { refreshRemote = false, silent = false } = options;
    if (!silent) {
      loading.value = true;
    }
    error.value = "";

    try {
      const slavesPromise = refreshRemote ? refreshSlaves() : listSlaves();
      const workersPromise = refreshRemote ? slavesPromise.then(() => listWorkers()) : listWorkers();
      const [nextHealth, nextWorkers, nextJobs, nextSlaves] = await Promise.all([
        getHealth(),
        workersPromise,
        listJobs(),
        slavesPromise
      ]);
      health.value = nextHealth;
      workers.value = nextWorkers;
      slaves.value = nextSlaves;
      jobs.value = nextJobs;
      lastUpdatedAt.value = new Date();
    } catch (caught) {
      error.value = caught.message;
    } finally {
      loading.value = false;
    }
  }

  async function createManagedSlave(payload) {
    return runAction("正在创建 Playwright 环境...", () => createBrowserEnvironment(payload), true);
  }

  async function attachSlave(payload) {
    return runAction("正在注册 slave...", () => registerSlave(payload), true);
  }

  async function removeWorker(workerId) {
    return runAction(`正在删除 ${workerId}...`, () => deleteWorker(workerId), true);
  }

  async function createJob(payload) {
    const job = await runAction("正在提交任务...", () => submitJob(payload), false);
    latestResult.value = job;
    await refresh({ silent: true });
    return job;
  }

  async function runAction(pendingMessage, action, refreshRemote) {
    message.value = pendingMessage;
    error.value = "";
    try {
      const result = await action();
      message.value = "操作完成";
      await refresh({ refreshRemote, silent: true });
      return result;
    } catch (caught) {
      error.value = caught.message;
      message.value = "";
      throw caught;
    }
  }

  function startPolling() {
    stopPolling();
    timer = window.setInterval(() => refresh({ silent: true }), 3000);
  }

  function stopPolling() {
    if (timer) {
      window.clearInterval(timer);
      timer = null;
    }
  }

  onBeforeUnmount(stopPolling);

  return {
    health,
    workers,
    slaves,
    remoteWorkers,
    jobs,
    jobCounts,
    latestResult,
    loading,
    message,
    error,
    lastUpdatedAt,
    refresh,
    createManagedSlave,
    attachSlave,
    removeWorker,
    createJob,
    startPolling,
    stopPolling
  };
}
