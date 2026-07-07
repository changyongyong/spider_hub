<script setup>
import { computed, reactive, ref } from "vue";
import { ArrowLeft, ChevronDown, Monitor, Smartphone } from "lucide-vue-next";
import SegmentedControl from "../ui/SegmentedControl.vue";

const emit = defineEmits(["cancel", "submit"]);

const sections = [
  { key: "basic", label: "基础设置" },
  { key: "proxy", label: "代理信息" },
  { key: "account", label: "账号信息" },
  { key: "advanced", label: "高级设置" }
];

const activeSection = ref("basic");
const form = reactive({
  env_name: "新建环境",
  count: 1,
  host: "127.0.0.1",
  port: "",
  browser_channel: "chrome",
  headful: true,
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
    return [];
  }
}

function launchArgs() {
  return form.launchArgsText
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function payload() {
  return {
    env_name: form.env_name,
    host: form.host,
    port: form.port ? Number(form.port) : undefined,
    browser_channel: form.browser_channel || undefined,
    headful: form.headful,
    challenge_wait: Number(form.challenge_wait),
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
    cookies: parseCookies()
  };
}

function submit() {
  emit("submit", payload());
}
</script>

<template>
  <div class="min-h-screen bg-white">
    <div class="flex h-14 items-center border-b border-line px-5">
      <button class="inline-flex items-center gap-1 text-sm text-muted hover:text-ink" type="button" @click="emit('cancel')">
        <ArrowLeft class="h-4 w-4" aria-hidden="true" />
        返回
      </button>
    </div>

    <div class="flex h-[calc(100vh-56px)]">
      <aside class="w-36 border-r border-line px-4 py-5">
        <div class="mb-5 flex gap-5 text-sm">
          <span class="inline-flex items-center gap-1 border-b-2 border-blue-500 pb-2 font-semibold text-blue-600">
            <Monitor class="h-4 w-4" aria-hidden="true" />
            浏览器
          </span>
          <span class="inline-flex items-center gap-1 pb-2 text-muted">
            <Smartphone class="h-4 w-4" aria-hidden="true" />
            云手机
          </span>
        </div>
        <nav class="grid gap-1 text-sm">
          <button
            v-for="section in sections"
            :key="section.key"
            class="border-l-2 px-3 py-2 text-left"
            :class="activeSection === section.key ? 'border-blue-500 font-semibold text-ink' : 'border-transparent text-slate-600 hover:bg-slate-50'"
            type="button"
            @click="activeSection = section.key"
          >
            {{ section.label }}
          </button>
        </nav>
      </aside>

      <main class="grid flex-1 grid-cols-[minmax(0,1fr)_360px] overflow-hidden">
        <form class="overflow-y-auto px-7 py-6" @submit.prevent="submit">
          <section v-show="activeSection === 'basic'" class="grid gap-5">
            <header class="flex h-9 items-center justify-between bg-slate-100 px-4 text-sm font-semibold">
              基础设置
              <ChevronDown class="h-4 w-4 text-muted" aria-hidden="true" />
            </header>
            <label class="label">
              环境名称 *
              <input v-model.trim="form.env_name" class="input max-w-4xl" required>
            </label>
            <div class="grid max-w-4xl gap-4 md:grid-cols-4">
              <label class="label">
                启动 Host
                <input v-model.trim="form.host" class="input">
              </label>
              <label class="label">
                指定端口
                <input v-model="form.port" class="input" type="number" placeholder="自动">
              </label>
              <label class="label">
                等待秒数
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

          <section v-show="activeSection === 'proxy'" class="grid gap-5">
            <header class="flex h-9 items-center justify-between bg-slate-100 px-4 text-sm font-semibold">
              代理信息
              <ChevronDown class="h-4 w-4 text-muted" aria-hidden="true" />
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

          <section v-show="activeSection === 'account'" class="grid gap-5">
            <header class="flex h-9 items-center justify-between bg-slate-100 px-4 text-sm font-semibold">
              账号信息
              <ChevronDown class="h-4 w-4 text-muted" aria-hidden="true" />
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

          <section v-show="activeSection === 'advanced'" class="grid gap-5 pb-24">
            <header class="flex h-9 items-center justify-between bg-slate-100 px-4 text-sm font-semibold">
              高级设置
              <ChevronDown class="h-4 w-4 text-muted" aria-hidden="true" />
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
