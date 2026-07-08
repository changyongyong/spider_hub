<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import { AlertCircle, Boxes, Filter, Loader2, LogOut, Play, Plus, RefreshCw, Search, TestTube2 } from "lucide-vue-next";
import SummaryStrip from "./components/dashboard/SummaryStrip.vue";
import SlaveEnvironmentForm from "./components/slaves/SlaveEnvironmentForm.vue";
import WorkerTable from "./components/slaves/WorkerTable.vue";
import { apiBaseUrl, apiProxyTarget, clearAuthSession, getAuthSession, setAuthSession } from "./api/http";
import { fetchUrl, login, logout } from "./api/masterApi";
import { useDashboard } from "./composables/useDashboard";

const dashboard = useDashboard();
const mode = ref("list");
const activeMenu = ref("environments");
const registerUrl = ref("");
const selectedEnvironment = ref(null);
const session = ref(getAuthSession());
const loginForm = reactive({ username: "", password: "" });
const loginError = ref("");
const loginLoading = ref(false);
const testForm = reactive({
  url: "",
  worker_id: "",
  wait_seconds: 3
});
const testLoading = ref(false);
const testError = ref("");
const testResult = ref(null);
const refreshIntervals = [
  { label: "关闭", value: 0 },
  { label: "3 秒", value: 3000 },
  { label: "5 秒", value: 5000 },
  { label: "10 秒", value: 10000 },
  { label: "30 秒", value: 30000 }
];
const apiTarget = apiBaseUrl || apiProxyTarget || "same-origin";
const runningWorkers = computed(() => dashboard.workers.value.filter((worker) => worker.running));
const testResultText = computed(() => (testResult.value ? JSON.stringify(testResult.value, null, 2) : ""));

onMounted(async () => {
  window.addEventListener("spider-auth-expired", handleAuthExpired);
  if (session.value) {
    await dashboard.refresh();
    dashboard.startPolling();
  }
});

onBeforeUnmount(() => {
  window.removeEventListener("spider-auth-expired", handleAuthExpired);
});

async function createEnvironment(payload) {
  if (mode.value === "edit" && selectedEnvironment.value) {
    await dashboard.updateManagedSlave(selectedEnvironment.value.worker_id, payload);
  } else {
    await dashboard.createManagedSlave(payload);
  }
  selectedEnvironment.value = null;
  mode.value = "list";
}

async function openCreateEnvironment() {
  await dashboard.refresh({ refreshRemote: true, silent: true });
  selectedEnvironment.value = null;
  mode.value = "create";
}

async function openEditEnvironment(worker) {
  const workerId = worker.worker_id;
  await dashboard.refresh({ refreshRemote: true, silent: true });
  selectedEnvironment.value = dashboard.workers.value.find((item) => item.worker_id === workerId) || worker;
  mode.value = "edit";
}

function closeEnvironmentForm() {
  selectedEnvironment.value = null;
  mode.value = "list";
}

async function saveQuickEnvironment({ workerId, payload }) {
  await dashboard.updateManagedSlave(workerId, payload);
}

async function toggleEnvironment(worker) {
  if (worker.running) {
    await dashboard.stopManagedSlave(worker.worker_id);
    return;
  }
  await dashboard.startManagedSlave(worker.worker_id);
}

async function testFetch() {
  testError.value = "";
  testResult.value = null;
  if (!testForm.url.trim()) {
    testError.value = "请输入要测试的 URL";
    return;
  }

  testLoading.value = true;
  try {
    testResult.value = await fetchUrl({
      url: testForm.url.trim(),
      worker_id: testForm.worker_id || undefined,
      wait_seconds: Number(testForm.wait_seconds),
      include_html: false,
      include_links: true
    });
    await dashboard.refresh({ silent: true });
  } catch (caught) {
    testError.value = caught.message;
  } finally {
    testLoading.value = false;
  }
}

async function registerExisting() {
  if (!registerUrl.value.trim()) return;
  await dashboard.attachSlave({ base_url: registerUrl.value.trim() });
  registerUrl.value = "";
}

function changeRefreshInterval(event) {
  dashboard.startPolling(Number(event.target.value));
}

async function submitLogin() {
  loginLoading.value = true;
  loginError.value = "";
  try {
    const nextSession = await login(loginForm);
    setAuthSession(nextSession);
    session.value = nextSession;
    loginForm.password = "";
    await dashboard.refresh();
    dashboard.startPolling();
  } catch (caught) {
    loginError.value = caught.message;
  } finally {
    loginLoading.value = false;
  }
}

async function signOut() {
  try {
    await logout();
  } catch {
    // Local logout still clears the browser session.
  }
  clearAuthSession();
  dashboard.stopPolling();
  mode.value = "list";
  activeMenu.value = "environments";
  selectedEnvironment.value = null;
  session.value = null;
}

function handleAuthExpired() {
  dashboard.stopPolling();
  mode.value = "list";
  activeMenu.value = "environments";
  selectedEnvironment.value = null;
  session.value = null;
}
</script>

<template>
  <SlaveEnvironmentForm
    v-if="session && (mode === 'create' || mode === 'edit')"
    :nodes="dashboard.slaves.value"
    :error="dashboard.error.value"
    :environment="selectedEnvironment"
    :mode="mode"
    @cancel="closeEnvironmentForm"
    @submit="createEnvironment"
  />

  <div v-else-if="!session" class="flex min-h-screen items-center justify-center bg-slate-100 px-4">
    <form class="panel grid w-full max-w-sm gap-4 p-6" @submit.prevent="submitLogin">
      <div>
        <h1 class="text-xl font-semibold text-ink">Spider Master</h1>
        <p class="mt-1 text-sm text-muted">登录后管理 slave 节点和 Playwright 环境。</p>
      </div>
      <label class="label">
        账号
        <input v-model.trim="loginForm.username" class="input" autocomplete="username" required>
      </label>
      <label class="label">
        密码
        <input v-model="loginForm.password" class="input" autocomplete="current-password" type="password" required>
      </label>
      <div v-if="loginError" class="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
        {{ loginError }}
      </div>
      <button class="btn h-10" type="submit" :disabled="loginLoading">
        <Loader2 v-if="loginLoading" class="h-4 w-4 animate-spin" aria-hidden="true" />
        登录
      </button>
      <p class="text-xs text-muted">API: {{ apiTarget }}</p>
    </form>
  </div>

  <div v-else class="min-h-screen">
    <header class="border-b border-line bg-white px-5 py-2">
      <div class="mx-auto flex max-w-[1500px] flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 class="text-lg font-semibold text-ink">Spider Master Console</h1>
          <p class="mt-0.5 text-xs text-muted">Slave 环境列表和浏览器启动环境管理。API: {{ apiTarget }}</p>
        </div>
        <div class="flex flex-wrap items-center gap-2 text-sm text-muted">
          <span>{{ session.username }}</span>
          <span>{{ dashboard.lastUpdatedAt.value ? dashboard.lastUpdatedAt.value.toLocaleString() : "等待刷新" }}</span>
          <select class="input h-9 w-28" :value="dashboard.refreshIntervalMs.value" @change="changeRefreshInterval">
            <option v-for="item in refreshIntervals" :key="item.value" :value="item.value">
              {{ item.label }}
            </option>
          </select>
          <button class="btn btn-secondary h-9" type="button" @click="dashboard.refresh({ refreshRemote: true })">
            <RefreshCw class="h-4 w-4" aria-hidden="true" />
            刷新
          </button>
          <button class="btn btn-secondary h-9" type="button" @click="signOut">
            <LogOut class="h-4 w-4" aria-hidden="true" />
            退出
          </button>
        </div>
      </div>
    </header>

    <main v-if="mode === 'list'" class="mx-auto grid max-w-[1500px] grid-cols-[168px_minmax(0,1fr)] gap-4 px-4 py-4">
      <aside class="panel self-start p-2">
        <nav class="grid gap-1 text-sm">
          <button
            class="flex h-9 items-center gap-2 rounded px-3"
            :class="activeMenu === 'environments' ? 'bg-blue-50 font-semibold text-blue-600' : 'text-slate-600 hover:bg-slate-50 hover:text-ink'"
            type="button"
            @click="activeMenu = 'environments'"
          >
            <Boxes class="h-4 w-4" aria-hidden="true" />
            我的环境
          </button>
          <button
            class="flex h-9 items-center gap-2 rounded px-3"
            :class="activeMenu === 'test' ? 'bg-blue-50 font-semibold text-blue-600' : 'text-slate-600 hover:bg-slate-50 hover:text-ink'"
            type="button"
            @click="activeMenu = 'test'"
          >
            <TestTube2 class="h-4 w-4" aria-hidden="true" />
            测试抓取
          </button>
        </nav>
      </aside>

      <div v-if="activeMenu === 'environments'" class="grid gap-4">
      <SummaryStrip
        :health="dashboard.health.value"
        :worker-count="dashboard.workers.value.length"
        :job-count="dashboard.jobs.value.length"
      />

      <div v-if="dashboard.error.value" class="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
        <AlertCircle class="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
        <span>{{ dashboard.error.value }}</span>
      </div>

      <div v-if="dashboard.message.value" class="rounded-lg border border-line bg-white px-4 py-3 text-sm text-muted shadow-panel">
        <span class="inline-flex items-center gap-2">
          <Loader2 v-if="dashboard.loading.value" class="h-4 w-4 animate-spin" aria-hidden="true" />
          {{ dashboard.message.value }}
        </span>
      </div>

      <section class="panel">
        <div class="flex flex-wrap items-center justify-between gap-3 border-b border-line px-3 py-3">
          <div class="flex flex-wrap items-center gap-2">
            <button class="btn bg-blue-600 hover:bg-blue-700" type="button" @click="openCreateEnvironment">
              <Plus class="h-4 w-4" aria-hidden="true" />
              新建环境
            </button>
            <form class="flex items-center gap-2" @submit.prevent="registerExisting">
              <input v-model.trim="registerUrl" class="input w-72" placeholder="注册已有 slave: http://127.0.0.1:8101">
              <button class="btn btn-secondary" type="submit">注册</button>
            </form>
          </div>
          <div class="flex items-center gap-2">
            <div class="relative">
              <Search class="absolute left-3 top-2.5 h-4 w-4 text-muted" aria-hidden="true" />
              <input class="input w-64 pl-9" placeholder="请输入环境名称">
            </div>
            <button class="btn btn-secondary">
              <Filter class="h-4 w-4" aria-hidden="true" />
              筛选
            </button>
          </div>
        </div>
        <div class="p-3">
          <WorkerTable
            :workers="dashboard.workers.value"
            @delete="dashboard.removeWorker"
            @edit="openEditEnvironment"
            @quick-save="saveQuickEnvironment"
            @toggle="toggleEnvironment"
          />
        </div>
      </section>
      </div>

      <div v-else class="grid gap-4">
        <section class="panel">
          <form class="grid gap-3 border-b border-line px-3 py-3 lg:grid-cols-[minmax(0,1fr)_220px_120px_auto]" @submit.prevent="testFetch">
            <label class="label gap-1">
              测试 URL
              <input v-model.trim="testForm.url" class="input" placeholder="https://example.com" type="url">
            </label>
            <label class="label gap-1">
              环境
              <select v-model="testForm.worker_id" class="input">
                <option value="">自动选择运行中环境</option>
                <option v-for="worker in runningWorkers" :key="worker.worker_id" :value="worker.worker_id">
                  {{ worker.env_name || worker.config?.env_name || worker.worker_id }}
                </option>
              </select>
            </label>
            <label class="label gap-1">
              等待秒数
              <input v-model="testForm.wait_seconds" class="input" min="0" type="number">
            </label>
            <div class="flex items-end">
              <button class="btn h-9 min-w-24" type="submit" :disabled="testLoading">
                <Loader2 v-if="testLoading" class="h-4 w-4 animate-spin" aria-hidden="true" />
                <Play v-else class="h-4 w-4" aria-hidden="true" />
                测试
              </button>
            </div>
          </form>
          <div v-if="testError" class="border-b border-line px-3 py-2 text-sm text-red-700">
            {{ testError }}
          </div>
          <div class="grid gap-2 px-3 py-3">
            <label class="label gap-1">
              返回信息
              <textarea
                class="input h-[calc(100vh-330px)] min-h-80 resize-none py-2 font-mono text-xs leading-5"
                readonly
                :value="testResultText"
                placeholder="测试完成后返回信息会显示在这里"
              ></textarea>
            </label>
          </div>
        </section>
      </div>
    </main>
  </div>
</template>
