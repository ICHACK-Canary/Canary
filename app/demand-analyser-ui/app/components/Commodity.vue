<script setup lang="ts">
import { Chart, registerables } from 'chart.js';

type Props = {
  name: string;
  country: string;
  delta: number;
  score: number;
  historicalScores: number[];
}

const {
  name,
  country,
  delta,
  score,
  historicalScores
} = defineProps<Props>();

const formattedDelta = delta > 0 ? `+${delta}` : `${delta}`;
const deltaColor = delta > 0 ? 'text-green-400' : 'text-red-400';

const sparkline = useTemplateRef<HTMLCanvasElement>('sparkline');

onMounted(() => {
  Chart.register(...registerables);
  if (!sparkline.value) return;

  new Chart(sparkline.value, {
      type: 'line',
      data: {
        labels: historicalScores.map((_, i) => i),
        datasets: [{
          label: 'Score',
          data: historicalScores,
          borderColor: delta > 0 ? 'oklch(79.2% 0.209 151.711)' : 'oklch(70.4% 0.191 22.216)',
          borderWidth: 2,
          tension: 0.1,
          fill: false,
          pointRadius: 0
        }]
      },
      options: {
        responsive: false,
        maintainAspectRatio: true,
        plugins: {
          legend: {
            display: false
          },
          title: {
            display: false
          }
        },
        scales: {
          x: {
            display: false
          },
          y: {
            display: false,
            beginAtZero: false
          }
        }
      }
  });
})
</script>

<style scoped>
.sparkline {
  width: 80px;
  height: 24px;
}
</style>

<template>
  <div class="border border-muted hover:border-red-400 hover:bg-red-400/10 flex justify-between items-center py-2 px-4">
    <div class="flex gap-2 items-center">
      <div>
        <strong>{{ name }}</strong>
        <div class="flex justify-between gap-3">
          <span class="text-muted">{{ country }}</span>
          <span :class="deltaColor">{{ formattedDelta }}</span>
        </div>
      </div>

      <canvas class="sparkline" ref="sparkline" width="80" height="24"></canvas>

      <span :class="deltaColor">{{ score }}</span>
    </div>
  </div>
</template>