<template>
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path v-for="(path, index) in paths[name] || paths.music" :key="index" :d="path" />
  </svg>
</template>

<script setup>
defineProps({ name: { type: String, default: 'music' } })
const paths = {
  music: ['M9 18V5l12-2v13', 'M9 8l12-2', 'M9 18c0 1.7-1.8 3-4 3s-3-1-3-2.5S3.8 16 6 16c1.1 0 2.2.3 3 1', 'M21 16c0 1.7-1.8 3-4 3s-3-1-3-2.5 1.8-2.5 4-2.5c1.1 0 2.2.3 3 1'],
  library: ['M4 5v15M9 3v17M14 5v15M18 4l4 15'],
  compass: ['M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20', 'm16 8-2.5 5.5L8 16l2.5-5.5Z'],
  search: ['M21 21l-5-5', 'M10.5 18a7.5 7.5 0 1 0 0-15 7.5 7.5 0 0 0 0 15'],
  list: ['M4 6h16M4 12h11M4 18h11', 'M20 12v9m-3-3h6'],
  upload: ['M12 16V3m-5 5 5-5 5 5', 'M4 16v5h16v-5'],
  plus: ['M12 5v14M5 12h14'],
  arrow: ['M5 12h14m-5-5 5 5-5 5'],
  back: ['M19 12H5m5-5-5 5 5 5'],
  chevron: ['m9 5 7 7-7 7'],
  play: ['m9 5 11 7-11 7Z'],
  pause: ['M8 5v14M16 5v14'],
  previous: ['M5 5v14m14-14-10 7 10 7Z'],
  next: ['M19 5v14M5 5l10 7-10 7Z'],
  volume: ['M11 4 6 8H2v8h4l5 4Z', 'M15 8a6 6 0 0 1 0 8m3-11a10 10 0 0 1 0 14'],
  clock: ['M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20', 'M12 6v6l4 2'],
  lock: ['M5 11h14v10H5Z', 'M8 11V7a4 4 0 0 1 8 0v4'],
  shield: ['m12 2 8 4v6c0 5-8 10-8 10S4 17 4 12V6Z', 'm8 12 3 3 5-6'],
  logout: ['M9 3H3v18h6', 'M8 12h13m-5-5 5 5-5 5'],
  menu: ['M4 6h16M4 12h16M4 18h16'],
  close: ['m6 6 12 12M6 18 18 6'],
  grid: ['M3 3h7v7H3ZM14 3h7v7h-7ZM3 14h7v7H3ZM14 14h7v7h-7Z'],
  rows: ['M8 5h13M8 12h13M8 19h13M3 5h.01M3 12h.01M3 19h.01'],
  headphones: ['M3 15v-3a9 9 0 0 1 18 0v3', 'M3 13h4v8H3ZM17 13h4v8h-4Z'],
  check: ['m5 12 4 4L19 6'],
}
</script>
