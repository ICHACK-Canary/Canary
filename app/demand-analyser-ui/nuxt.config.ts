import tailwindcss from "@tailwindcss/vite";

export default defineNuxtConfig({
  compatibilityDate: "2025-07-15",
  devtools: { enabled: true },
  css: ["@/assets/css/main.css"],
  vite: {
    plugins: [
      // @ts-expect-error this works but types aren't recognized
      tailwindcss(),
    ],
  },
  modules: ["@nuxt/ui"],
  runtimeConfig: {
    public: {
      apiBase: "http://localhost:8000",
    },
  },
});