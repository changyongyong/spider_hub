<script setup>
import { reactive, ref } from "vue";
import { Edit3, Eye, EyeOff, MoreVertical, Network, Power, Settings2, Trash2 } from "lucide-vue-next";
import { workerStatus } from "../../domain/dashboard";
import StatusBadge from "../ui/StatusBadge.vue";

defineProps({
  workers: {
    type: Array,
    required: true
  }
});

const emit = defineEmits(["delete", "edit", "quick-save", "toggle"]);
const openMenuId = ref("");
const menuWorker = ref(null);
const menuPosition = ref({ top: 0, left: 0 });
const quickMode = ref("");
const quickWorker = ref(null);
const quickError = ref("");
const showQuickProxyPassword = ref(false);
const quickProxy = reactive({
  enabled: false,
  scheme: "http",
  host: "",
  port: "",
  username: "",
  password: ""
});
const quickConfig = reactive({
  env_name: "",
  browser_channel: "",
  headful: false,
  challenge_wait: 0,
  locale: "",
  timezone_id: "",
  viewport_width: 1365,
  viewport_height: 768,
  user_agent: "",
  block_images: false,
  block_media: false,
  launchArgsText: ""
});

function addressOf(worker) {
  const proxy = worker.config?.proxy || worker.proxy;
  if (proxy && typeof proxy === "object") {
    if (proxy.enabled === false) return "直连";
    return proxy.server || `${proxy.scheme || "http"}://${proxy.host}:${proxy.port}`;
  }
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
  return [browserOf(worker), locale, timezone, viewport];
}

function toggleMenu(worker, event) {
  if (openMenuId.value === worker.worker_id) {
    closeMenu();
    return;
  }

  const rect = event.currentTarget.getBoundingClientRect();
  const menuWidth = 144;
  openMenuId.value = worker.worker_id;
  menuWorker.value = worker;
  menuPosition.value = {
    top: rect.bottom + 6,
    left: Math.max(8, Math.min(rect.right - menuWidth, window.innerWidth - menuWidth - 8))
  };
}

function closeMenu() {
  openMenuId.value = "";
  menuWorker.value = null;
}

function edit(worker) {
  closeMenu();
  emit("edit", worker);
}

function openQuickProxy(worker) {
  closeMenu();
  quickMode.value = "proxy";
  quickWorker.value = worker;
  quickError.value = "";
  showQuickProxyPassword.value = false;
  fillQuickProxy(worker.config?.proxy || worker.proxy);
}

function openQuickConfig(worker) {
  closeMenu();
  quickMode.value = "config";
  quickWorker.value = worker;
  quickError.value = "";
  const config = worker.config || {};
  quickConfig.env_name = envName(worker);
  quickConfig.browser_channel = config.browser_channel || worker.browser_channel || "";
  quickConfig.headful = Boolean(config.headful ?? worker.headful ?? false);
  quickConfig.challenge_wait = Number(config.challenge_wait ?? worker.challenge_wait ?? 0);
  quickConfig.locale = config.locale || "";
  quickConfig.timezone_id = config.timezone_id || "";
  quickConfig.viewport_width = Number(config.viewport_width || 1365);
  quickConfig.viewport_height = Number(config.viewport_height || 768);
  quickConfig.user_agent = config.user_agent || "";
  quickConfig.block_images = Boolean(config.block_images);
  quickConfig.block_media = Boolean(config.block_media);
  quickConfig.launchArgsText = Array.isArray(config.launch_args) ? config.launch_args.join("\n") : "";
}

function fillQuickProxy(proxy) {
  quickProxy.enabled = Boolean(proxy && proxy !== "direct" && proxy !== "直连" && proxy.enabled !== false);
  quickProxy.scheme = "http";
  quickProxy.host = "";
  quickProxy.port = "";
  quickProxy.username = "";
  quickProxy.password = "";
  if (!quickProxy.enabled) return;

  if (typeof proxy === "object") {
    const parsed = parseProxyServer(proxy.server || "");
    const host = proxy.host || parsed.host || "";
    const port = proxy.port ? String(proxy.port) : parsed.port || "";
    if (!host || !port) {
      quickProxy.enabled = false;
      return;
    }
    quickProxy.scheme = proxy.scheme || parsed.scheme || "http";
    quickProxy.host = host;
    quickProxy.port = port;
    quickProxy.username = proxy.username || parsed.username || "";
    quickProxy.password = proxy.password || parsed.password || "";
    return;
  }

  const parsed = parseProxyServer(proxy);
  if (!parsed.host || !parsed.port) return;
  quickProxy.scheme = parsed.scheme;
  quickProxy.host = parsed.host;
  quickProxy.port = parsed.port;
  quickProxy.username = parsed.username || "";
  quickProxy.password = parsed.password || "";
}

function closeQuickEdit() {
  quickMode.value = "";
  quickWorker.value = null;
  quickError.value = "";
  showQuickProxyPassword.value = false;
}

function saveQuickEdit() {
  quickError.value = "";
  if (!quickWorker.value) return;
  if (quickMode.value === "proxy" && quickProxy.enabled && (!quickProxy.host || !quickProxy.port)) {
    quickError.value = "请填写代理主机和端口";
    return;
  }
  emit("quick-save", {
    workerId: quickWorker.value.worker_id,
    payload: quickPayload()
  });
  closeQuickEdit();
}

function quickPayload() {
  const worker = quickWorker.value;
  const config = worker.config || {};
  const proxy = quickMode.value === "proxy" ? quickProxyPayload() : proxyFromCurrent(config.proxy || worker.proxy);
  return {
    node_id: worker.node_id,
    env_name: quickMode.value === "config" ? quickConfig.env_name : envName(worker),
    browser_channel: quickMode.value === "config" ? quickConfig.browser_channel || undefined : config.browser_channel || worker.browser_channel || undefined,
    headful: quickMode.value === "config" ? quickConfig.headful : Boolean(config.headful ?? worker.headful ?? false),
    challenge_wait: quickMode.value === "config" ? Number(quickConfig.challenge_wait) : Number(config.challenge_wait ?? worker.challenge_wait ?? 0),
    proxy,
    launch_args: quickMode.value === "config" ? launchArgs() : config.launch_args || [],
    user_agent: quickMode.value === "config" ? quickConfig.user_agent : config.user_agent,
    locale: quickMode.value === "config" ? quickConfig.locale : config.locale,
    timezone_id: quickMode.value === "config" ? quickConfig.timezone_id : config.timezone_id,
    viewport_width: quickMode.value === "config" ? Number(quickConfig.viewport_width) : config.viewport_width,
    viewport_height: quickMode.value === "config" ? Number(quickConfig.viewport_height) : config.viewport_height,
    block_images: quickMode.value === "config" ? quickConfig.block_images : Boolean(config.block_images),
    block_media: quickMode.value === "config" ? quickConfig.block_media : Boolean(config.block_media),
    cookies: config.cookies || [],
    platform: config.platform,
    start_url: config.start_url,
    webrtc: config.webrtc,
    canvas: config.canvas,
    webgl_image: config.webgl_image,
    webgl_info: config.webgl_info,
    webgpu: config.webgpu,
    audio_context: config.audio_context,
    speech_voices: config.speech_voices,
    media_devices: config.media_devices,
    hardware_concurrency: config.hardware_concurrency,
    device_memory: config.device_memory,
    do_not_track: config.do_not_track,
    port_scan_protection: config.port_scan_protection
  };
}

function quickProxyPayload() {
  return {
    enabled: quickProxy.enabled,
    scheme: quickProxy.scheme,
    host: quickProxy.host || undefined,
    port: quickProxy.port ? Number(quickProxy.port) : undefined,
    username: quickProxy.username || undefined,
    password: quickProxy.password || undefined
  };
}

function proxyFromCurrent(proxy) {
  if (!proxy || proxy === "direct" || proxy === "直连" || proxy.enabled === false) {
    return { enabled: false };
  }
  if (typeof proxy === "object") {
    const parsed = parseProxyServer(proxy.server || "");
    const host = proxy.host || parsed.host;
    const port = proxy.port ? Number(proxy.port) : parsed.port ? Number(parsed.port) : undefined;
    if (!host || !port) return { enabled: false };
    return {
      enabled: true,
      scheme: proxy.scheme || parsed.scheme || "http",
      host,
      port,
      username: proxy.username || parsed.username || undefined,
      password: proxy.password || parsed.password || undefined
    };
  }
  const parsed = parseProxyServer(proxy);
  if (!parsed.host || !parsed.port) return { enabled: false };
  return {
    enabled: true,
    scheme: parsed.scheme,
    host: parsed.host,
    port: Number(parsed.port),
    username: parsed.username || undefined,
    password: parsed.password || undefined
  };
}

function parseProxyServer(server) {
  try {
    const parsed = new URL(String(server));
    if (!["http:", "https:", "socks5:"].includes(parsed.protocol) || !parsed.hostname || !parsed.port) {
      return { scheme: "", host: "", port: "", username: "", password: "" };
    }
    return {
      scheme: parsed.protocol.replace(":", ""),
      host: parsed.hostname,
      port: parsed.port,
      username: decodeURIComponent(parsed.username || ""),
      password: decodeURIComponent(parsed.password || "")
    };
  } catch {
    return { scheme: "", host: "", port: "", username: "", password: "" };
  }
}

function launchArgs() {
  return quickConfig.launchArgsText
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}
</script>

<template>
  <div class="max-h-[calc(100vh-260px)] overflow-auto">
    <table class="w-full min-w-[1060px] table-fixed border-collapse">
      <thead class="table-head">
        <tr>
          <th class="table-cell w-[40px]"></th>
          <th class="table-cell w-[250px]">环境</th>
          <th class="table-cell w-[150px]">代理</th>
          <th class="table-cell">配置</th>
          <th class="table-cell w-[92px]">状态</th>
          <th class="table-cell w-[100px]">请求</th>
          <th class="table-cell w-[180px]">最近活动</th>
          <th class="table-cell w-[112px] text-right">操作</th>
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
            <div class="font-medium leading-5 text-ink">{{ envName(worker) }}</div>
            <div class="mt-0.5 font-mono text-xs leading-4 text-blue-600">{{ worker.worker_id }}</div>
            <div class="truncate text-xs leading-4 text-muted">{{ worker.kind === "remote" ? worker.base_url : "local" }}</div>
          </td>
          <td class="table-cell">
            <span class="inline-flex max-w-full items-center rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-700">
              <span class="truncate">{{ addressOf(worker) }}</span>
            </span>
          </td>
          <td class="table-cell">
            <div class="flex flex-wrap gap-1">
              <span
                v-for="item in configLine(worker)"
                :key="item"
                class="rounded border border-line bg-white px-1.5 py-0.5 text-xs leading-4 text-slate-700"
              >
                {{ item }}
              </span>
            </div>
          </td>
          <td class="table-cell">
            <StatusBadge :tone="workerStatus(worker).tone">{{ workerStatus(worker).text }}</StatusBadge>
          </td>
          <td class="table-cell">{{ worker.stats?.requests || 0 }} / 失败 {{ worker.stats?.failures || 0 }}</td>
          <td class="table-cell">
            <div class="max-h-8 overflow-hidden break-words text-xs leading-4 text-slate-600">{{ lastActivity(worker) }}</div>
          </td>
          <td class="table-cell text-right">
            <div class="relative inline-flex gap-1.5">
              <button
                class="h-7 w-7 rounded border px-0"
                :class="worker.running ? 'border-amber-300 bg-amber-50 text-amber-700 hover:bg-amber-100' : 'border-emerald-300 bg-emerald-50 text-emerald-700 hover:bg-emerald-100'"
                type="button"
                :title="worker.running ? `关闭 ${worker.worker_id}` : `启动 ${worker.worker_id}`"
                @click="emit('toggle', worker)"
              >
                <Power class="mx-auto h-3.5 w-3.5" aria-hidden="true" />
              </button>
              <button class="btn btn-danger h-7 w-7 px-0" type="button" :title="`删除 ${worker.worker_id}`" @click="emit('delete', worker.worker_id)">
                <Trash2 class="h-3.5 w-3.5" aria-hidden="true" />
              </button>
              <button class="h-7 w-7 rounded border border-line text-muted hover:bg-slate-50" type="button" title="更多" @click="toggleMenu(worker, $event)">
                <MoreVertical class="mx-auto h-3.5 w-3.5" aria-hidden="true" />
              </button>
            </div>
          </td>
        </tr>
      </tbody>
    </table>
  </div>

  <Teleport to="body">
    <div
      v-if="menuWorker"
      class="fixed inset-0 z-[9998]"
      @click="closeMenu"
      @wheel.passive="closeMenu"
    ></div>
    <div
      v-if="menuWorker"
      class="fixed z-[9999] grid w-36 overflow-hidden rounded border border-line bg-white py-1 text-left text-sm shadow-lg"
      :style="{ top: `${menuPosition.top}px`, left: `${menuPosition.left}px` }"
    >
      <button class="flex items-center gap-2 px-3 py-2 hover:bg-slate-50" type="button" @click="edit(menuWorker)">
        <Edit3 class="h-4 w-4 text-muted" aria-hidden="true" />
        编辑环境
      </button>
      <button class="flex items-center gap-2 px-3 py-2 hover:bg-slate-50" type="button" @click="openQuickProxy(menuWorker)">
        <Network class="h-4 w-4 text-muted" aria-hidden="true" />
        编辑代理
      </button>
      <button class="flex items-center gap-2 px-3 py-2 hover:bg-slate-50" type="button" @click="openQuickConfig(menuWorker)">
        <Settings2 class="h-4 w-4 text-muted" aria-hidden="true" />
        编辑配置
      </button>
    </div>

    <div v-if="quickWorker" class="fixed inset-0 z-[10000] flex items-start justify-center bg-slate-900/20 px-4 pt-24" @click.self="closeQuickEdit">
      <form class="grid w-full max-w-xl gap-4 rounded border border-line bg-white p-4 shadow-lg" @submit.prevent="saveQuickEdit">
        <div class="flex items-center justify-between">
          <h3 class="text-base font-semibold text-ink">{{ quickMode === "proxy" ? "编辑代理" : "编辑配置" }}</h3>
          <button class="text-sm text-muted hover:text-ink" type="button" @click="closeQuickEdit">关闭</button>
        </div>

        <div v-if="quickError" class="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {{ quickError }}
        </div>

        <div v-if="quickMode === 'proxy'" class="grid gap-3">
          <label class="flex items-center gap-2 text-sm text-slate-700">
            <input v-model="quickProxy.enabled" class="h-4 w-4" type="checkbox">
            启用代理
          </label>
          <div class="grid gap-2 md:grid-cols-8">
            <select v-model="quickProxy.scheme" class="input md:col-span-2">
              <option value="http">HTTP</option>
              <option value="https">HTTPS</option>
              <option value="socks5">SOCKS5</option>
            </select>
            <input v-model.trim="quickProxy.host" class="input md:col-span-4" placeholder="代理主机">
            <input v-model="quickProxy.port" class="input md:col-span-2" type="number" placeholder="端口">
          </div>
          <div class="grid gap-2 md:grid-cols-8">
            <input v-model.trim="quickProxy.username" class="input md:col-span-4" placeholder="账号">
            <span class="relative block w-full md:col-span-4">
              <button
                class="absolute inset-y-0 right-2 z-10 flex w-6 items-center justify-center text-muted hover:text-ink"
                type="button"
                :title="showQuickProxyPassword ? '隐藏密码' : '查看密码'"
                @click="showQuickProxyPassword = !showQuickProxyPassword"
              >
                <EyeOff v-if="showQuickProxyPassword" class="h-4 w-4" aria-hidden="true" />
                <Eye v-else class="h-4 w-4" aria-hidden="true" />
              </button>
              <input
                v-model.trim="quickProxy.password"
                class="input w-full pr-9"
                placeholder="密码"
                :type="showQuickProxyPassword ? 'text' : 'password'"
              >
            </span>
          </div>
        </div>

        <div v-else class="grid gap-3">
          <input v-model.trim="quickConfig.env_name" class="input" placeholder="环境名称">
          <div class="grid gap-2 md:grid-cols-2">
            <select v-model="quickConfig.browser_channel" class="input">
              <option value="">Chromium</option>
              <option value="chrome">Chrome</option>
              <option value="msedge">Edge</option>
            </select>
            <input v-model="quickConfig.challenge_wait" class="input" type="number" min="0" placeholder="等待秒数">
          </div>
          <div class="grid gap-2 md:grid-cols-2">
            <input v-model.trim="quickConfig.locale" class="input" placeholder="语言">
            <input v-model.trim="quickConfig.timezone_id" class="input" placeholder="时区">
          </div>
          <div class="grid gap-2 md:grid-cols-2">
            <input v-model="quickConfig.viewport_width" class="input" type="number" placeholder="宽度">
            <input v-model="quickConfig.viewport_height" class="input" type="number" placeholder="高度">
          </div>
          <input v-model.trim="quickConfig.user_agent" class="input" placeholder="User Agent">
          <textarea v-model="quickConfig.launchArgsText" class="input h-20 py-2" placeholder="启动参数，每行一个"></textarea>
          <div class="flex flex-wrap gap-4 text-sm text-slate-700">
            <label class="flex items-center gap-2">
              <input v-model="quickConfig.headful" class="h-4 w-4" type="checkbox">
              有头模式
            </label>
            <label class="flex items-center gap-2">
              <input v-model="quickConfig.block_images" class="h-4 w-4" type="checkbox">
              禁图片
            </label>
            <label class="flex items-center gap-2">
              <input v-model="quickConfig.block_media" class="h-4 w-4" type="checkbox">
              禁媒体
            </label>
          </div>
        </div>

        <div class="flex justify-end gap-2">
          <button class="btn btn-secondary" type="button" @click="closeQuickEdit">取消</button>
          <button class="btn" type="submit">保存</button>
        </div>
      </form>
    </div>
  </Teleport>
</template>
