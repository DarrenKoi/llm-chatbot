// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  ssr: false,
  modules: ['@nuxt/ui'],
  app: {
    baseURL: '/chat/',
    head: {
      title: 'LLM Chatbot',
      meta: [
        { charset: 'utf-8' },
        { name: 'viewport', content: 'width=device-width, initial-scale=1' },
      ],
    },
  },
  runtimeConfig: {
    public: {
      webChatApiBase: '/api/v1/web-chat',
    },
  },
  devServer: {
    port: 3000,
  },
  nitro: {
    output: {
      publicDir: '.output/public',
    },
    devProxy: {
      '/api': {
        target: 'http://localhost:5000/api',
        changeOrigin: true,
      },
    },
  },
  compatibilityDate: '2025-01-01',
})
