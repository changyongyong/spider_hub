<script setup>
import { Activity, BriefcaseBusiness, Server } from "lucide-vue-next";

defineProps({
  health: {
    type: Object,
    required: true
  },
  workerCount: {
    type: Number,
    required: true
  },
  jobCount: {
    type: Number,
    required: true
  }
});

const metrics = [
  { key: "master", label: "Master", icon: Activity },
  { key: "workers", label: "Workers", icon: Server },
  { key: "jobs", label: "Jobs", icon: BriefcaseBusiness }
];
</script>

<template>
  <section class="panel flex flex-wrap items-center divide-y divide-line md:divide-x md:divide-y-0">
    <div v-for="metric in metrics" :key="metric.key" class="flex min-w-48 flex-1 items-center gap-3 px-4 py-3">
      <span class="inline-flex h-8 w-8 items-center justify-center rounded bg-slate-100 text-muted">
        <component :is="metric.icon" class="h-4 w-4" aria-hidden="true" />
      </span>
      <div>
        <div class="text-xs font-medium text-muted">{{ metric.label }}</div>
        <strong class="block text-xl font-semibold leading-6 text-ink">
          <template v-if="metric.key === 'master'">{{ health.ok ? "OK" : "DOWN" }}</template>
          <template v-else-if="metric.key === 'workers'">{{ workerCount }}</template>
          <template v-else>{{ jobCount }}</template>
        </strong>
      </div>
    </div>
  </section>
</template>
