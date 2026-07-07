<script setup>
import { MoreVertical, Trash2 } from "lucide-vue-next";
import { workerStatus } from "../../domain/dashboard";
import StatusBadge from "../ui/StatusBadge.vue";

defineProps({
  workers: {
    type: Array,
    required: true
  }
});

const emit = defineEmits(["delete"]);

function addressOf(worker) {
  const proxy = worker.config?.proxy || worker.proxy;
  return proxy && proxy !== "direct" ? proxy : "直连";
}

function lastActivity(worker) {
  return worker.last_error || worker.stats?.last_error || worker.stats?.last_url || "-";
}

function envName(worker) {
  return worker.env_name || worker.config?.env_name || worker.worker_id;
}

function browserOf(worker) {
  const channel = worker.config?.browser_channel || worker.browser_channel;
  if (channel === "chrome") return "Chrome";
  if (channel === "msedge") return "Edge";
  return "Chromium";
}

function configLine(worker) {
  const config = worker.config || {};
  const viewport = config.viewport_width && config.viewport_height ? `${config.viewport_width}x${config.viewport_height}` : "默认分辨率";
  const locale = config.locale || "默认语言";
  const timezone = config.timezone_id || "默认时区";
  return `${browserOf(worker)} | ${locale} | ${timezone} | ${viewport}`;
}
</script>

<template>
  <div class="overflow-x-auto">
    <table class="w-full min-w-[1080px] table-fixed border-collapse">
      <thead class="table-head">
        <tr>
          <th class="table-cell w-[56px]"></th>
          <th class="table-cell w-[240px]">环境</th>
          <th class="table-cell w-[220px]">代理</th>
          <th class="table-cell">配置</th>
          <th class="table-cell w-[110px]">状态</th>
          <th class="table-cell w-[120px]">请求</th>
          <th class="table-cell w-[180px]">最近活动</th>
          <th class="table-cell w-[120px]">操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="workers.length === 0">
          <td class="table-cell text-muted" colspan="8">暂无 slave 环境，点击新建环境开始。</td>
        </tr>
        <tr v-for="worker in workers" :key="worker.worker_id">
          <td class="table-cell">
            <input class="h-4 w-4" type="checkbox">
          </td>
          <td class="table-cell">
            <div class="font-medium text-ink">{{ envName(worker) }}</div>
            <div class="mt-1 text-xs text-muted">{{ worker.worker_id }}</div>
            <div class="mt-1 text-xs text-muted">{{ worker.kind === "remote" ? worker.base_url : "local" }}</div>
          </td>
          <td class="table-cell">
            {{ addressOf(worker) }}
          </td>
          <td class="table-cell">{{ configLine(worker) }}</td>
          <td class="table-cell">
            <StatusBadge :tone="workerStatus(worker).tone">{{ workerStatus(worker).text }}</StatusBadge>
          </td>
          <td class="table-cell">{{ worker.stats?.requests || 0 }} / 失败 {{ worker.stats?.failures || 0 }}</td>
          <td class="table-cell">{{ lastActivity(worker) }}</td>
          <td class="table-cell">
            <div class="flex gap-2">
              <button class="h-8 rounded border border-blue-500 px-3 text-sm text-blue-600 hover:bg-blue-50" type="button">
                切换
              </button>
              <button class="btn btn-danger h-8 w-8 px-0" type="button" :title="`删除 ${worker.worker_id}`" @click="emit('delete', worker.worker_id)">
              <Trash2 class="h-4 w-4" aria-hidden="true" />
              </button>
              <button class="h-8 w-8 rounded border border-line text-muted hover:bg-slate-50" type="button" title="更多">
                <MoreVertical class="mx-auto h-4 w-4" aria-hidden="true" />
              </button>
            </div>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
