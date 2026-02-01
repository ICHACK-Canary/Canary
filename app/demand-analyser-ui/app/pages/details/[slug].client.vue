<script setup lang="ts">
import { Chart, registerables } from 'chart.js';

const route = useRoute();
const slug = route.params.slug as string;
const config = useRuntimeConfig();
const apiBase = config.public.apiBase;

const fallbackData = [
  { date: 'Jan 23', score: 2340 },
  { date: 'Feb 23', score: 2550 },
  { date: 'Mar 23', score: 2730 },
  { date: 'Apr 23', score: 2950 },
  { date: 'May 23', score: 3120 },
  { date: 'Jun 23', score: 3300 },
  { date: 'Jul 23', score: 3500 },
  { date: 'Aug 23', score: 3700 },
  { date: 'Sep 23', score: 3900 },
  { date: 'Oct 23', score: 3800 },
  { date: 'Nov 23', score: 3300 },
  { date: 'Dec 23', score: 2000 }
]

const chartCanvas = useTemplateRef<HTMLCanvasElement>('chartCanvas');

onMounted(async () => {
  if (chartCanvas.value) {
    const data = await $fetch<{ date: string; score: number }[]>(
      `${apiBase}/details/${slug}`
    ).catch(() => fallbackData);
    Chart.register(...registerables);
    
    new Chart(chartCanvas.value, {
      type: 'line',
      data: {
        labels: data.map(item => item.date),
        datasets: [{
          label: 'Score',
          data: data.map(item => item.score),
          borderColor: 'rgb(75, 192, 192)',
          backgroundColor: 'rgba(75, 192, 192, 0.2)',
          tension: 0.1,
          fill: true
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: true,
            position: 'top'
          },
          title: {
            display: true,
            text: `Demand Analysis - ${slug}`
          }
        },
        scales: {
          y: {
            beginAtZero: false
          }
        }
      }
    });
  }
});

definePageMeta({
  validate(route) {
    return typeof route.params.slug === 'string';
  }
})
</script>

<template>
  <div class="container">
    <h1>{{ slug }}</h1>
    <div class="chart-container">
      <canvas ref="chartCanvas"></canvas>
    </div>
  </div>
</template>

<style scoped>
.container {
  padding: 2rem;
  max-width: 1200px;
  margin: 0 auto;
}

h1 {
  margin-bottom: 2rem;
  text-transform: capitalize;
}

.chart-container {
  height: 400px;
  width: 100%;
}
</style>