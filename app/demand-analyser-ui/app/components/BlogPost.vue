<script setup lang="ts">
import type { BlogItem } from '#shared/types/blogs';

const {
  title,
  timeAgo,
  content,
  location,
  likes,
  viral = false
} = defineProps<BlogItem>();
</script>

<template>
  <div class="border py-2 px-2 rounded-xl" :class="viral ? 'border-red-400 bg-red-400/10' : 'border-muted'">
    <span v-if="viral" class="text-red-400 mb-2 flex items-center">
      <UIcon name="i-lucide-bolt" class="inline-block mr-1" />
      <strong class="uppercase">Viral Alert</strong>
    </span>
    <div class="flex justify-between gap-2">
      <h4 class="w-3/4 text-balance">{{ title }}</h4>
      <span class="text-end">{{ timeAgo }}</span>
    </div>

    <USeparator class="my-2" />

    <p>{{ content }}</p>

    <div class="mt-4 w-full flex justify-between">
      <div class="flex items-center  text-muted">
        <UIcon name="i-lucide-map-pin" />
        <span class="ml-2">{{ location }}</span>
      </div>
      <div class="flex items-center  text-red-400 font-bold">
        <UIcon name="i-lucide-heart" />
        <span class="ml-2">{{ likes }}</span>
      </div>
    </div>
  </div>
</template>