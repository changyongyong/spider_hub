<script setup>
defineProps({
  modelValue: {
    type: String,
    required: true
  },
  label: {
    type: String,
    required: true
  },
  options: {
    type: Array,
    required: true
  }
});

defineEmits(["update:modelValue"]);
</script>

<template>
  <div class="grid gap-2">
    <span class="text-sm text-muted">{{ label }}</span>
    <div class="flex flex-wrap gap-2">
      <button
        v-for="option in options"
        :key="option[0]"
        class="h-8 rounded border px-3 text-sm"
        :class="modelValue === option[0] ? 'border-blue-500 bg-blue-50 text-blue-600' : 'border-line bg-white text-slate-600 hover:bg-slate-50'"
        type="button"
        @click="$emit('update:modelValue', option[0])"
      >
        {{ option[1] }}
      </button>
    </div>
  </div>
</template>
