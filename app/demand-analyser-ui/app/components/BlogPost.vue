<script setup lang="ts">
import type { Alert } from '#shared/types/blogs';

const {
  id,
  timestamp,
  timeAgo,
  location,
  product,
  severity,
  severityLevel,
  severityScore,
  severityColor,
  metrics,
  socialPosts
} = defineProps<Alert>();

const viral = computed(() => {
  return severityLevel === 'HIGH' || severityLevel === 'ELEVATED' || severityLevel === 'CRITICAL';
});
</script>

<template>
  <div class="border py-2 px-2 rounded-xl my-2" :class="viral ? 'border-red-400 bg-red-400/10' : 'border-muted'" v-for="post in socialPosts" :key="post.id">
    <span v-if="viral" class="text-red-400 mb-2 flex items-center">
      <UIcon name="i-lucide-bolt" class="inline-block mr-1" />
      <strong class="uppercase">Viral Alert</strong>
    </span>
    <div class="flex justify-between gap-2">
      <h4 class="w-3/4 text-balance" v-if="product">{{ product }}</h4>
      <span class="text-end">{{ timeAgo }}</span>
    </div>

    <p>{{ post.content }}</p>

    <div class="mt-4 flex items-center text-muted" v-if="location?.countryName">
      <UIcon name="i-lucide-map-pin" />
      <span class="ml-2">{{ location?.countryName }}</span>
    </div>
  </div>
</template>