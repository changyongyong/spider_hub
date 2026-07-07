<script setup>
const props = defineProps({
  tone: {
    type: String,
    default: "muted"
  }
});

const toneClasses = {
  ok: "bg-emerald-50 text-emerald-700",
  warn: "bg-amber-50 text-amber-700",
  danger: "bg-red-50 text-red-700",
  muted: "bg-slate-100 text-slate-600"
};
</script>

<template>
  <span class="inline-flex min-h-6 items-center rounded-full px-2.5 py-0.5 text-xs font-semibold" :class="toneClasses[props.tone] || toneClasses.muted">
    <slot />
  </span>
</template>
