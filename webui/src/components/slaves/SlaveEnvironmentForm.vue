<script setup>
import { computed, reactive, ref, watch } from "vue";
import { ArrowLeft, Monitor } from "lucide-vue-next";
import SegmentedControl from "../ui/SegmentedControl.vue";

const props = defineProps({
  nodes: {
    type: Array,
    default: () => []
  },
  error: {
    type: String,
    default: ""
  },
  environment: {
    type: Object,
    default: null
  },
  mode: {
    type: String,
    default: "create"
  }
});

const emit = defineEmits(["cancel", "submit"]);

const sections = [
  { key: "basic", label: "基础设置" },
  { key: "proxy", label: "代理信息" },
  { key: "account", label: "账号信息" },
  { key: "advanced", label: "高级设置" }
];

const localError = ref("");
const form = reactive({
  node_id: "",
  env_name: "新建环境",
  count: 1,
  browser_channel: "",
  headful: false,
  challenge_wait: 5,
  platform: "Windows",
  user_agent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.7499.109 Safari/537.36",
  locale: "pl-PL",
  timezone_id: "Europe/Warsaw",
  viewport_width: 1365,
  viewport_height: 768,
  proxy: {
    enabled: false,
    scheme: "http",
    host: "",
    port: "",
    username: "",
    password: ""
  },
  cookiesText: "",
  startUrl: "",
  webrtc: "hide",
  canvas: "noise",
  webgl_image: "noise",
  webgl_info: "ua",
  webgpu: "webgl",
  audio_context: "noise",
  speech_voices: "on",
  media_devices: "noise",
  hardware_concurrency: 4,
  device_memory: 4,
  do_not_track: "default",
  port_scan_protection: "on",
  launchArgsText: "--disable-notifications",
  block_images: false,
  block_media: false
});

const preview = computed(() => [
  ["浏览器", browserLabel(form.browser_channel)],
  ["操作系统", form.platform],
  ["User Agent", form.user_agent || "默认"],
  ["语言", form.locale || "跟随 IP 匹配"],
  ["时区", form.timezone_id || "跟随 IP 匹配"],
  ["分辨率", `${form.viewport_width} x ${form.viewport_height}`],
  ["代理", form.proxy.enabled ? `${form.proxy.scheme.toUpperCase()} ${form.proxy.host}:${form.proxy.port}` : "直连"],
  ["WebRTC", labelOf(form.webrtc)],
  ["Canvas", labelOf(form.canvas)],
  ["WebGL图像", labelOf(form.webgl_image)],
  ["WebGL Info", labelOf(form.webgl_info)],
  ["WebGPU", labelOf(form.webgpu)],
  ["AudioContext", labelOf(form.audio_context)],
  ["SpeechVoices", form.speech_voices === "on" ? "开启" : "关闭"],
  ["媒体设备", labelOf(form.media_devices)],
  ["硬件并发数", form.hardware_concurrency],
  ["设备内存", `${form.device_memory}GB`],
  ["Do Not Track", labelOf(form.do_not_track)],
  ["端口扫描保护", form.port_scan_protection === "on" ? "开启" : "关闭"]
]);
const visibleError = computed(() => localError.value || props.error);
const isEditing = computed(() => props.mode === "edit");
const pageTitle = computed(() => (isEditing.value ? "编辑环境" : "新建环境"));
const submitHint = computed(() => {
  if (!form.env_name.trim()) return "请先填写环境名称";
  if (!form.node_id) return "请选择一个可用的 slave 节点";
  if (form.proxy.enabled && (!form.proxy.host || !form.proxy.port)) return "代理已启用，请填写代理主机和端口";
  return "";
});

watch(
  () => props.environment,
  (environment) => {
    if (environment) {
      applyEnvironment(environment);
    }
  },
  { immediate: true }
);

function browserLabel(value) {
  if (value === "chrome") return "Chrome";
  if (value === "msedge") return "Microsoft Edge";
  return "Chromium";
}

function labelOf(value) {
  const labels = {
    default: "默认",
    real: "真实",
    noise: "噪音",
    hide: "隐藏",
    replace: "替换",
    disable: "禁用",
    ua: "基于UA匹配",
    webgl: "基于WebGL匹配",
    on: "开启",
    off: "关闭"
  };
  return labels[value] || value;
}

function buttonClass(value, expected) {
  return [
    "h-8 rounded border px-3 text-sm",
    value === expected ? "border-blue-500 bg-blue-50 text-blue-600" : "border-line bg-white text-slate-600 hover:bg-slate-50"
  ];
}

function parseCookies() {
  const text = form.cookiesText.trim();
  if (!text) return [];
  try {
    const parsed = JSON.parse(text);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    throw new Error("Cookie 必须是 Playwright cookies JSON 数组");
  }
}

function launchArgs() {
  return form.launchArgsText
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function applyEnvironment(environment) {
  const config = environment.config || {};
  form.node_id = environment.node_id || "";
  form.env_name = environment.env_name || config.env_name || environment.worker_id || "新建环境";
  form.browser_channel = config.browser_channel || environment.browser_channel || "";
  form.headful = Boolean(config.headful ?? environment.headful ?? false);
  form.challenge_wait = Number(config.challenge_wait ?? environment.challenge_wait ?? 5);
  form.platform = config.platform || form.platform;
  form.user_agent = config.user_agent || form.user_agent;
  form.locale = config.locale || form.locale;
  form.timezone_id = config.timezone_id || form.timezone_id;
  form.viewport_width = Number(config.viewport_width || form.viewport_width);
  form.viewport_height = Number(config.viewport_height || form.viewport_height);
  form.block_images = Boolean(config.block_images);
  form.block_media = Boolean(config.block_media);
  form.cookiesText = Array.isArray(config.cookies) ? JSON.stringify(config.cookies, null, 2) : "";
  form.startUrl = config.start_url || "";
  form.webrtc = config.webrtc || form.webrtc;
  form.canvas = config.canvas || form.canvas;
  form.webgl_image = config.webgl_image || form.webgl_image;
  form.webgl_info = config.webgl_info || form.webgl_info;
  form.webgpu = config.webgpu || form.webgpu;
  form.audio_context = config.audio_context || form.audio_context;
  form.speech_voices = config.speech_voices || form.speech_voices;
  form.media_devices = config.media_devices || form.media_devices;
  form.hardware_concurrency = Number(config.hardware_concurrency || form.hardware_concurrency);
  form.device_memory = Number(config.device_memory || form.device_memory);
  form.do_not_track = config.do_not_track || form.do_not_track;
  form.port_scan_protection = config.port_scan_protection || form.port_scan_protection;
  form.launchArgsText = Array.isArray(config.launch_args) ? config.launch_args.join("\n") : form.launchArgsText;
  applyProxy(config.proxy || environment.proxy);
}

function applyProxy(proxy) {
  if (!proxy || proxy === "direct" || proxy === "直连" || proxy.enabled === false) {
    form.proxy.enabled = false;
    form.proxy.host = "";
    form.proxy.port = "";
    form.proxy.username = "";
    form.proxy.password = "";
    return;
  }

  if (typeof proxy === "object") {
    const parsed = parseProxyServer(proxy.server || "");
    form.proxy.enabled = true;
    form.proxy.scheme = proxy.scheme || parsed.scheme || "http";
    form.proxy.host = proxy.host || parsed.host || "";
    form.proxy.port = proxy.port ? String(proxy.port) : parsed.port || "";
    form.proxy.username = proxy.username || "";
    form.proxy.password = proxy.password || "";
    return;
  }

  const match = String(proxy).match(/^(https?|socks5):\/\/([^:/]+):(\d+)$/);
  if (!match) return;
  form.proxy.enabled = true;
  form.proxy.scheme = match[1];
  form.proxy.host = match[2];
  form.proxy.port = match[3];
  form.proxy.username = "";
  form.proxy.password = "";
}

function parseProxyServer(server) {
  const match = String(server).match(/^(https?|socks5):\/\/([^:/]+):(\d+)$/);
  if (!match) return { scheme: "", host: "", port: "" };
  return { scheme: match[1], host: match[2], port: match[3] };
}

function payload() {
  return {
    node_id: form.node_id,
    env_name: form.env_name,
    browser_channel: form.browser_channel || undefined,
    headful: form.headful,
    challenge_wait: Number(form.challenge_wait),
    platform: form.platform,
    proxy: {
      ...form.proxy,
      port: form.proxy.port ? Number(form.proxy.port) : undefined
    },
    launch_args: launchArgs(),
    user_agent: form.user_agent,
    locale: form.locale,
    timezone_id: form.timezone_id,
    viewport_width: Number(form.viewport_width),
    viewport_height: Number(form.viewport_height),
    block_images: form.block_images,
    block_media: form.block_media,
    cookies: parseCookies(),
    start_url: form.startUrl,
    webrtc: form.webrtc,
    canvas: form.canvas,
    webgl_image: form.webgl_image,
    webgl_info: form.webgl_info,
    webgpu: form.webgpu,
    audio_context: form.audio_context,
    speech_voices: form.speech_voices,
    media_devices: form.media_devices,
    hardware_concurrency: Number(form.hardware_concurrency),
    device_memory: Number(form.device_memory),
    do_not_track: form.do_not_track,
    port_scan_protection: form.port_scan_protection
  };
}

function submit() {
  localError.value = "";
  if (!form.env_name.trim()) {
    localError.value = "请填写环境名称";
    return;
  }
  if (!form.node_id) {
    localError.value = "请选择 slave 节点";
    return;
  }
  if (form.proxy.enabled && (!form.proxy.host || !form.proxy.port)) {
    localError.value = "启用代理时必须填写代理主机和端口";
    return;
  }
  if (form.proxy.enabled) {
    const port = Number(form.proxy.port);
    if (!Number.isInteger(port) || port < 1 || port > 65535) {
      localError.value = "代理端口必须是 1-65535 的整数";
      return;
    }
  }
  try {
    parseCookies();
  } catch (caught) {
    localError.value = caught.message;
    return;
  }
  emit("submit", payload());
}

function nodeLabel(node) {
  const slots = node.available_slots ?? "-";
  const total = node.max_environments ?? node.max_workers ?? "-";
  return `${node.node_id} (${node.base_url}, ${slots}/${total} 可用)`;
}

function scrollToSection(key) {
  document.getElementById(`env-${key}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
}
</script>

<template>
  <div class="min-h-screen bg-white">
    <div class="flex h-14 items-center justify-between border-b border-line px-5">
      <button class="inline-flex items-center gap-1 text-sm text-muted hover:text-ink" type="button" @click="emit('cancel')">
        <ArrowLeft class="h-4 w-4" aria-hidden="true" />
        返回
      </button>
      <h1 class="text-base font-semibold text-ink">{{ pageTitle }}</h1>
      <div class="w-12"></div>
    </div>

    <div class="grid h-[calc(100vh-56px)] grid-cols-[150px_minmax(0,1fr)] overflow-hidden">
      <aside class="border-r border-line px-3 py-5">
        <nav class="grid gap-1 text-sm">
          <button
            v-for="section in sections"
            :key="section.key"
            class="rounded px-3 py-2 text-left text-slate-600 hover:bg-slate-50 hover:text-ink"
            type="button"
            @click="scrollToSection(section.key)"
          >
            {{ section.label }}
          </button>
        </nav>
      </aside>

      <main class="grid h-full grid-cols-[minmax(0,1fr)_360px] overflow-hidden">
        <form class="overflow-y-auto px-7 py-6" novalidate @submit.prevent="submit">
          <section id="env-basic" class="scroll-mt-4 grid gap-5 border-b border-line pb-7">
            <header class="flex h-9 items-center justify-between bg-slate-100 px-4 text-sm font-semibold">
              <span class="inline-flex items-center gap-2">
                <Monitor class="h-4 w-4 text-muted" aria-hidden="true" />
                基础设置
              </span>
              <button v-if="isEditing" class="h-7 rounded border border-line bg-white px-3 text-xs text-slate-600 hover:bg-slate-50" type="submit">保存此块</button>
            </header>
            <label class="label">
              环境名称 *
              <input v-model.trim="form.env_name" class="input max-w-4xl" required>
            </label>
            <label class="label max-w-4xl">
              Slave 节点 *
              <select v-model="form.node_id" class="input" :disabled="isEditing" required>
                <option value="" disabled>请选择承载该 Playwright 环境的 slave 节点</option>
                <option
                  v-for="node in props.nodes"
                  :key="node.node_id"
                  :value="node.node_id"
                >
                  {{ nodeLabel(node) }}
                </option>
              </select>
            </label>
            <div v-if="props.nodes.length === 0" class="max-w-4xl rounded border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-700">
              当前没有可用 slave 节点。请先启动或注册 slave 节点，再创建 Playwright 环境。
            </div>
            <div v-if="visibleError" class="max-w-4xl rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {{ visibleError }}
            </div>
            <div class="grid max-w-4xl gap-4 md:grid-cols-2">
              <label class="label">
                页面额外等待秒数
                <input v-model="form.challenge_wait" class="input" type="number" min="0">
              </label>
              <label class="label">
                有头模式
                <span class="flex h-9 items-center"><input v-model="form.headful" class="h-4 w-4" type="checkbox"></span>
              </label>
            </div>
            <div class="grid gap-2">
              <span class="text-sm text-muted">浏览器</span>
              <div class="flex gap-2">
                <button :class="buttonClass(form.browser_channel, 'chrome')" type="button" @click="form.browser_channel = 'chrome'">Chrome</button>
                <button :class="buttonClass(form.browser_channel, '')" type="button" @click="form.browser_channel = ''">Chromium</button>
                <button :class="buttonClass(form.browser_channel, 'msedge')" type="button" @click="form.browser_channel = 'msedge'">Edge</button>
              </div>
            </div>
            <div class="grid gap-2">
              <span class="text-sm text-muted">操作系统</span>
              <div class="flex gap-2">
                <button :class="buttonClass(form.platform, 'Windows')" type="button" @click="form.platform = 'Windows'">Windows</button>
                <button :class="buttonClass(form.platform, 'macOS')" type="button" @click="form.platform = 'macOS'">macOS</button>
                <button :class="buttonClass(form.platform, 'Android')" type="button" @click="form.platform = 'Android'">Android</button>
              </div>
            </div>
            <label class="label">
              User Agent
              <input v-model.trim="form.user_agent" class="input max-w-4xl">
            </label>
            <div class="grid max-w-4xl gap-4 md:grid-cols-3">
              <label class="label">
                语言
                <input v-model.trim="form.locale" class="input" placeholder="pl-PL">
              </label>
              <label class="label">
                时区
                <input v-model.trim="form.timezone_id" class="input" placeholder="Europe/Warsaw">
              </label>
              <label class="label">
                分辨率
                <span class="grid grid-cols-2 gap-2">
                  <input v-model="form.viewport_width" class="input" type="number">
                  <input v-model="form.viewport_height" class="input" type="number">
                </span>
              </label>
            </div>
          </section>

          <section id="env-proxy" class="scroll-mt-4 grid gap-5 border-b border-line py-7">
            <header class="flex h-9 items-center justify-between bg-slate-100 px-4 text-sm font-semibold">
              代理信息
              <button v-if="isEditing" class="h-7 rounded border border-line bg-white px-3 text-xs text-slate-600 hover:bg-slate-50" type="submit">保存此块</button>
            </header>
            <div class="grid gap-2">
              <span class="text-sm text-muted">代理方式</span>
              <div class="flex gap-2">
                <button :class="buttonClass(form.proxy.enabled, false)" type="button" @click="form.proxy.enabled = false">直连</button>
                <button :class="buttonClass(form.proxy.enabled, true)" type="button" @click="form.proxy.enabled = true">自定义</button>
              </div>
            </div>
            <div class="grid max-w-4xl gap-4 md:grid-cols-[180px_1fr_160px]">
              <label class="label">
                代理类型 *
                <select v-model="form.proxy.scheme" class="input">
                  <option value="http">HTTP</option>
                  <option value="https">HTTPS</option>
                  <option value="socks5">SOCKS5</option>
                </select>
              </label>
              <label class="label">
                代理主机 *
                <input v-model.trim="form.proxy.host" class="input" placeholder="请输入 IP 地址或域名">
              </label>
              <label class="label">
                代理端口 *
                <input v-model="form.proxy.port" class="input" type="number" placeholder="端口号">
              </label>
            </div>
            <div class="grid max-w-4xl gap-4 md:grid-cols-2">
              <label class="label">
                代理账号
                <input v-model.trim="form.proxy.username" class="input">
              </label>
              <label class="label">
                代理密码
                <input v-model.trim="form.proxy.password" class="input" type="password">
              </label>
            </div>
          </section>

          <section id="env-account" class="scroll-mt-4 grid gap-5 border-b border-line py-7">
            <header class="flex h-9 items-center justify-between bg-slate-100 px-4 text-sm font-semibold">
              账号信息
              <button v-if="isEditing" class="h-7 rounded border border-line bg-white px-3 text-xs text-slate-600 hover:bg-slate-50" type="submit">保存此块</button>
            </header>
            <label class="label">
              Cookie
              <textarea v-model.trim="form.cookiesText" class="input h-28 max-w-4xl py-2" placeholder="支持 Playwright cookies JSON 数组"></textarea>
            </label>
            <label class="label">
              打开指定网址
              <input v-model.trim="form.startUrl" class="input max-w-4xl" placeholder="预留字段，当前采集任务会动态传 URL">
            </label>
          </section>

          <section id="env-advanced" class="scroll-mt-4 grid gap-5 pb-24 pt-7">
            <header class="flex h-9 items-center justify-between bg-slate-100 px-4 text-sm font-semibold">
              高级设置
              <button v-if="isEditing" class="h-7 rounded border border-line bg-white px-3 text-xs text-slate-600 hover:bg-slate-50" type="submit">保存此块</button>
            </header>
            <div class="grid gap-4 md:grid-cols-2">
              <SegmentedControl v-model="form.webrtc" label="WebRTC" :options="[['hide','隐藏'],['replace','替换'],['real','真实'],['disable','禁用']]" />
              <SegmentedControl v-model="form.canvas" label="Canvas" :options="[['noise','噪音'],['real','真实']]" />
              <SegmentedControl v-model="form.webgl_image" label="WebGL图像" :options="[['noise','噪音'],['real','真实']]" />
              <SegmentedControl v-model="form.webgl_info" label="WebGL Info" :options="[['ua','基于UA匹配'],['real','真实']]" />
              <SegmentedControl v-model="form.webgpu" label="WebGPU" :options="[['webgl','基于WebGL匹配'],['real','真实'],['disable','禁用']]" />
              <SegmentedControl v-model="form.audio_context" label="AudioContext" :options="[['noise','噪音'],['real','真实']]" />
            </div>
            <div class="grid max-w-4xl gap-4 md:grid-cols-2">
              <label class="label">
                硬件并发数
                <input v-model="form.hardware_concurrency" class="input" type="number" min="1">
              </label>
              <label class="label">
                设备内存 GB
                <input v-model="form.device_memory" class="input" type="number" min="1">
              </label>
            </div>
            <div class="grid gap-2">
              <span class="text-sm text-muted">资源加载</span>
              <label class="flex items-center gap-2 text-sm text-slate-600">
                <input v-model="form.block_images" class="h-4 w-4" type="checkbox">
                禁止加载图片
              </label>
              <label class="flex items-center gap-2 text-sm text-slate-600">
                <input v-model="form.block_media" class="h-4 w-4" type="checkbox">
                禁止加载音视频
              </label>
            </div>
            <label class="label">
              启动参数
              <textarea v-model="form.launchArgsText" class="input h-28 max-w-4xl py-2" placeholder="每行一个 Chromium 启动参数"></textarea>
            </label>
          </section>

          <footer class="fixed bottom-0 left-0 right-0 flex h-14 items-center gap-2 border-t border-line bg-white px-5">
            <button class="btn min-w-24" type="submit">完成</button>
            <button class="btn btn-secondary min-w-20" type="button" @click="emit('cancel')">取消</button>
            <span v-if="submitHint" class="text-sm text-muted">{{ submitHint }}</span>
          </footer>
        </form>

        <aside class="border-l border-line bg-slate-50 p-5">
          <h3 class="mb-4 text-base font-semibold">环境预览</h3>
          <dl class="grid gap-3 text-sm">
            <div v-for="[label, value] in preview" :key="label" class="grid grid-cols-[96px_1fr] gap-2">
              <dt class="text-right text-muted">{{ label }}：</dt>
              <dd class="break-words text-slate-700">{{ value }}</dd>
            </div>
          </dl>
        </aside>
      </main>
    </div>
  </div>
</template>
