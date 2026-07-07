<script setup>
import { ref } from "vue";
import { onMounted } from "vue";
import { AlertCircle, Boxes, Filter, Loader2, Plus, RefreshCw, Search } from "lucide-vue-next";
import SummaryStrip from "./components/dashboard/SummaryStrip.vue";
import SlaveEnvironmentForm from "./components/slaves/SlaveEnvironmentForm.vue";
import WorkerTable from "./components/slaves/WorkerTable.vue";
import { useDashboard } from "./composables/useDashboard";

const dashboard = useDashboard();
const mode = ref("list");
const registerUrl = ref("");

onMounted(async () => {
  await dashboard.refresh();
  dashboard.startPolling();
});

async function createEnvironment(payload) {
  await dashboard.createManagedSlave(payload);
  mode.value = "list";
}

async function openCreateEnvironment() {
  await dashboard.refresh({ refreshRemote: true, silent: true });
  mode.value = "create";
}

async function registerExisting() {
  if (!registerUrl.value.trim()) return;
  await dashboard.attachSlave({ base_url: registerUrl.value.trim() });
  registerUrl.value = "";
}
</script>

<template>
  <SlaveEnvironmentForm
    v-if="mode === 'create'"
    :nodes="dashboard.slaves.value"
    @cancel="mode = 'list'"
    @submit="createEnvironment"
  />

  <div v-else class="min-h-screen">
    <header class="border-b border-line bg-white px-6 py-3">
      <div class="mx-auto flex max-w-[1500px] flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 class="text-xl font-semibold text-ink">Spider Master Console</h1>
          <p class="mt-1 text-sm text-muted">Slave 环境列表和浏览器启动环境管理。</p>
        </div>
        <div class="text-sm text-muted">
          {{ dashboard.lastUpdatedAt.value ? dashboard.lastUpdatedAt.value.toLocaleString() : "等待刷新" }}
        </div>
      </div>
    </header>

    <main v-if="mode === 'list'" class="mx-auto grid max-w-[1500px] grid-cols-[180px_minmax(0,1fr)] gap-5 px-5 py-5">
      <aside class="panel min-h-[calc(100vh-112px)] p-3">
        <nav class="grid gap-1 text-sm">
          <button class="flex h-10 items-center gap-2 rounded bg-blue-50 px-3 font-semibold text-blue-600" type="button">
            <Boxes class="h-4 w-4" aria-hidden="true" />
            我的环境
          </button>
          <button class="flex h-10 items-center gap-2 rounded px-3 text-muted hover:bg-slate-50" type="button">常用环境</button>
          <button class="flex h-10 items-center gap-2 rounded px-3 text-muted hover:bg-slate-50" type="button">最近打开</button>
          <button class="flex h-10 items-center gap-2 rounded px-3 text-muted hover:bg-slate-50" type="button">环境分组</button>
          <button class="flex h-10 items-center gap-2 rounded px-3 text-muted hover:bg-slate-50" type="button">回收站</button>
        </nav>
      </aside>

      <div class="grid gap-5">
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
        <div class="flex flex-wrap items-center justify-between gap-3 border-b border-line p-4">
          <div class="flex flex-wrap items-center gap-2">
            <button class="btn bg-blue-600 hover:bg-blue-700" type="button" @click="openCreateEnvironment">
              <Plus class="h-4 w-4" aria-hidden="true" />
              新建环境
            </button>
            <form class="flex items-center gap-2" @submit.prevent="registerExisting">
              <input v-model.trim="registerUrl" class="input w-72" placeholder="注册已有 slave: http://127.0.0.1:8101">
              <button class="btn btn-secondary" type="submit">注册</button>
            </form>
            <button class="btn btn-secondary w-9 px-0" type="button" title="刷新" @click="dashboard.refresh({ refreshRemote: true })">
              <RefreshCw class="h-4 w-4" aria-hidden="true" />
            </button>
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
        <div class="p-4">
          <WorkerTable :workers="dashboard.workers.value" @delete="dashboard.removeWorker" />
        </div>
      </section>
      </div>
    </main>
  </div>
</template>
