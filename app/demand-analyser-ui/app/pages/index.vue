<script setup lang="ts">
import type { GetAlertsResponse } from '~~/shared/types/blogs';

const body = useTemplateRef<HTMLElement>('body');
const config = useRuntimeConfig();
const apiBase = config.public.apiBase;

const fallbackAlerts: GetAlertsResponse = {
  count: 5,
  alerts: [
    {
      id: '2024-01-30T10:00:00_US_Semiconductors',
      timestamp: '2024-01-30T10:00:00Z',
      timeAgo: '2 hours ago',
      location: {
        country: 'US',
        countryName: 'United States',
        lat: 37.7749,
        lng: -122.4194
      },
      product: 'Semiconductors',
      severity: 'CONFIRMED',
      severityLevel: 'HIGH',
      severityScore: 75,
      severityColor: '#ea580c',
      metrics: {
        searches: 8500,
        y: 1200,
        slope: 45,
        accel: 12,
        level_z: 2.5,
        accel_z: 8
      },
      socialPosts: [
        {
          id: 'tweet1',
          content: 'Global chip shortage continues to impact tech industry',
          originalText: 'The ongoing global chip shortage continues to affect the technology sector, leading to delays in product launches and increased prices for consumers.',
          author: 'Tech Reporter',
          timestamp: '2024-01-30T10:00:00Z',
          sentiment: 'negative',
          sentimentScore: -0.85,
          keywords: ['chip', 'shortage', 'tech', 'delays']
        }
      ]
    },
    {
      id: '2024-01-29T15:30:00_DE_Materials',
      timestamp: '2024-01-29T15:30:00Z',
      timeAgo: '1 day ago',
      location: {
        country: 'DE',
        countryName: 'Germany',
        lat: 51.1657,
        lng: 10.4515
      },
      product: 'Industrial Materials',
      severity: 'EARLY',
      severityLevel: 'ELEVATED',
      severityScore: 50,
      severityColor: '#ca8a04',
      metrics: {
        searches: 6200,
        y: 950,
        slope: 32,
        accel: 8,
        level_z: 1.8,
        accel_z: 5.2
      },
      socialPosts: [
        {
          id: 'tweet2',
          content: 'Supply chain disruptions affecting manufacturing sector',
          originalText: 'Manufacturers worldwide are facing delays due to supply chain disruptions caused by the pandemic and geopolitical tensions.',
          author: 'Supply Chain News',
          timestamp: '2024-01-29T15:30:00Z',
          sentiment: 'negative',
          sentimentScore: -0.72,
          keywords: ['supply chain', 'disruption', 'manufacturing', 'delays']
        }
      ]
    },
    {
      id: '2024-01-27T08:15:00_NO_Batteries',
      timestamp: '2024-01-27T08:15:00Z',
      timeAgo: '3 days ago',
      location: {
        country: 'NO',
        countryName: 'Norway',
        lat: 60.4720,
        lng: 8.4689
      },
      product: 'Batteries',
      severity: 'CONFIRMED',
      severityLevel: 'CRITICAL',
      severityScore: 100,
      severityColor: '#dc2626',
      metrics: {
        searches: 9800,
        y: 1500,
        slope: 58,
        accel: 15,
        level_z: 3.2,
        accel_z: 10.5
      },
      socialPosts: [
        {
          id: 'tweet3',
          content: 'Rising demand for EV batteries strains supply',
          originalText: 'The surge in demand for electric vehicles is putting pressure on battery suppliers, leading to concerns about meeting future production targets.',
          author: 'Energy Sector Analyst',
          timestamp: '2024-01-27T08:15:00Z',
          sentiment: 'negative',
          sentimentScore: -0.65,
          keywords: ['battery', 'EV', 'demand', 'supply', 'shortage']
        }
      ]
    },
    {
      id: '2024-01-29T14:20:00_BR_Agriculture',
      timestamp: '2024-01-29T14:20:00Z',
      timeAgo: '1 day ago',
      location: {
        country: 'BR',
        countryName: 'Brazil',
        lat: -14.2350,
        lng: -51.9253
      },
      product: 'Agricultural Inputs',
      severity: 'EARLY',
      severityLevel: 'WATCH',
      severityScore: 25,
      severityColor: '#2563eb',
      metrics: {
        searches: 4500,
        y: 720,
        slope: 18,
        accel: 4,
        level_z: 0.9,
        accel_z: 2.1
      },
      socialPosts: [
        {
          id: 'tweet4',
          content: 'Agricultural supply concerns in South America',
          originalText: 'Farmers across South America report concerns about input availability affecting crop production.',
          author: 'Agricultural News',
          timestamp: '2024-01-29T14:20:00Z',
          sentiment: 'negative',
          sentimentScore: -0.55,
          keywords: ['agriculture', 'supply', 'inputs', 'production']
        }
      ]
    },
    {
      id: '2024-01-29T12:45:00_JP_Electronics',
      timestamp: '2024-01-29T12:45:00Z',
      timeAgo: '1 day ago',
      location: {
        country: 'JP',
        countryName: 'Japan',
        lat: 36.2048,
        lng: 138.2529
      },
      product: 'Electronics Components',
      severity: 'CONFIRMED',
      severityLevel: 'HIGH',
      severityScore: 75,
      severityColor: '#ea580c',
      metrics: {
        searches: 7600,
        y: 1100,
        slope: 42,
        accel: 11,
        level_z: 2.3,
        accel_z: 7.8
      },
      socialPosts: [
        {
          id: 'tweet5',
          content: 'Electronics component shortage impacts production',
          originalText: 'Japanese electronics manufacturers report component supply challenges affecting assembly lines.',
          author: 'Tech Industry Reports',
          timestamp: '2024-01-29T12:45:00Z',
          sentiment: 'negative',
          sentimentScore: -0.68,
          keywords: ['electronics', 'components', 'shortage', 'production']
        }
      ]
    }
  ]
}

const fallbackCommodities = [
  { name: 'Eggs', country: 'Taiwan', delta: 15, score: 2000, historicalScores: [1300, 1400, 1350, 1750, 2000] },
  { name: 'Chicken', country: 'Brazil', delta: 10, score: 2200, historicalScores: [1500, 1600, 1700, 2000, 2200] },
  { name: 'Rice', country: 'India', delta: -5, score: 1700, historicalScores: [1200, 1250, 1300, 1600, 1700].reverse() },
  { name: 'Toilet paper', country: 'South Korea', delta: -8, score: 1500, historicalScores: [1100, 1150, 1200, 1400, 1500].reverse() },
  { name: 'Milk', country: 'USA', delta: 5, score: 1800, historicalScores: [1300, 1350, 1400, 1700, 1800] },
  { name: 'Bread', country: 'China', delta: -12, score: 1300, historicalScores: [1000, 1050, 1100, 1200, 1300].reverse() },
]

const { data: alerts } = await useFetch<GetAlertsResponse>(`${apiBase}/alerts`, {
  default: () => fallbackAlerts,
  server: false
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

          <div v-if="!alerts?.alerts || alerts.count == 0" class="text-center text-muted text-lg uppercase mt-8">
            Nothing to see here...
          </div>
          <UScrollArea v-else v-slot="{ item }" :items="alerts?.alerts" class="w-full h-full">
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