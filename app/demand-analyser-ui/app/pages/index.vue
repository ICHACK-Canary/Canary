<script setup lang="ts">
import { Chart, registerables } from 'chart.js';
const body = useTemplateRef<HTMLElement>('body');
const config = useRuntimeConfig();
const apiBase = config.public.apiBase;

const fallbackBlogs: BlogItem[] = [
  {
    title: 'Global chip shortage impacts tech industry',
    timeAgo: '2 hours ago',
    content: 'The ongoing global chip shortage continues to affect the technology sector, leading to delays in product launches and increased prices for consumers.',
    location: 'Silicon Valley, CA',
    likes: '120',
    viral: true
  },
  {
    title: 'Supply chain disruptions cause delays in manufacturing',
    timeAgo: '1 day ago',
    content: 'Manufacturers worldwide are facing delays due to supply chain disruptions caused by the pandemic and geopolitical tensions.',
    location: 'Detroit, MI',
    likes: '85'
  },
  {
    title: 'Rising demand for electric vehicles strains battery supply',
    timeAgo: '3 days ago',
    content: 'The surge in demand for electric vehicles is putting pressure on battery suppliers, leading to concerns about meeting future production targets.',
    location: 'Oslo, Norway',
    likes: '95',
    viral: true
  },
  {
    title: 'Supply chain disruptions cause delays in manufacturing',
    timeAgo: '1 day ago',
    content: 'Manufacturers worldwide are facing delays due to supply chain disruptions caused by the pandemic and geopolitical tensions.',
    location: 'Detroit, MI',
    likes: '85'
  },
  {
    title: 'Supply chain disruptions cause delays in manufacturing',
    timeAgo: '1 day ago',
    content: 'Manufacturers worldwide are facing delays due to supply chain disruptions caused by the pandemic and geopolitical tensions.',
    location: 'Detroit, MI',
    likes: '85'
  },
]

const fallbackCommodities = [
  { name: 'Eggs', country: 'Taiwan', delta: 15, score: 2000, historicalScores: [1300, 1400, 1350, 1750, 2000] },
  { name: 'Chicken', country: 'Brazil', delta: 10, score: 2200, historicalScores: [1500, 1600, 1700, 2000, 2200] },
  { name: 'Rice', country: 'India', delta: -5, score: 1700, historicalScores: [1200, 1250, 1300, 1600, 1700].reverse() },
  { name: 'Toilet paper', country: 'South Korea', delta: -8, score: 1500, historicalScores: [1100, 1150, 1200, 1400, 1500].reverse() },
  { name: 'Milk', country: 'USA', delta: 5, score: 1800, historicalScores: [1300, 1350, 1400, 1700, 1800] },
  { name: 'Bread', country: 'China', delta: -12, score: 1300, historicalScores: [1000, 1050, 1100, 1200, 1300].reverse() },
]

const { data: blogs } = await useFetch<BlogItem[]>(`${apiBase}/feed`, {
  default: () => fallbackBlogs,
  server: false,
});

const { data: commodities } = await useFetch<{
  name: string;
  country: string;
  delta: number;
  score: number;
  historicalScores: number[];
}[]>(`${apiBase}/commodities`, {
  default: () => fallbackCommodities,
  server: false,
});

</script>

<template>
  <UDashboardPanel>
    <template #header>
      <UDashboardNavbar>
        <template #title>
          <div class="flex flex-col">
            <h1 class="text-xl">Shortage</h1>
            <h4 class="text-sm font-normal">Global supply intelligence</h4>
          </div>
        </template>

        <template #leading>
          <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
            class="lucide lucide-activity w-5 h-5 text-background">
            <path
              d="M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.25.25 0 0 1-.48 0L9.24 2.18a.25.25 0 0 0-.48 0l-2.35 8.36A2 2 0 0 1 4.49 12H2">
            </path>
          </svg>
        </template>

        <template #right>
          <UBadge label="LIVE" color="error" variant="outline" icon="i-lucide-radio" size="md" />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="grid grid-cols-4 gap-4" ref="body" :style="{ height: `calc(90vh - ${body?.clientTop}px)` }">
        <div class="col-span-1 h-full border rounded-xl border-muted p-4 overflow-y-hidden">
          <div class="flex items-center gap-2">
            <UIcon name="i-lucide-satellite-dish" />
            <h3>Social media feed</h3>
          </div>

          <USeparator class="my-2" />

          <UScrollArea v-slot="{ item }" :items="blogs" class="w-full h-full">
            <BlogPost v-bind="item" class="my-2" />
          </UScrollArea>
        </div>

        <div class="col-span-3 h-full w-full">
          <div class="border border-muted py-4 rounded-xl">
            <UMarquee :overlay="false" :ui="{ root: '[--gap:--spacing(1)]', content: 'w-auto py-1' }">
              <div class="flex gap-4 px-4">
                <Commodity v-for="commodity in commodities" :key="commodity.name" v-bind="commodity" />
              </div>
            </UMarquee>
          </div>

          <div class="border border-muted rounded-xl mt-4">
            <Globe />
          </div>
        </div>
      </div>
    </template>
  </UDashboardPanel>
</template>