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
  <section class="grid gap-3 md:grid-cols-3">
    <div v-for="metric in metrics" :key="metric.key" class="panel min-h-24 p-4">
      <div class="flex items-center justify-between text-sm text-muted">
        <span>{{ metric.label }}</span>
        <component :is="metric.icon" class="h-4 w-4" aria-hidden="true" />
      </div>
      <strong class="mt-3 block text-3xl font-semibold">
        <template v-if="metric.key === 'master'">{{ health.ok ? "OK" : "DOWN" }}</template>
        <template v-else-if="metric.key === 'workers'">{{ workerCount }}</template>
        <template v-else>{{ jobCount }}</template>
      </strong>
    </div>
  </section>
</template>
