import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'
import { PRODUCT_NAME } from './src/config.ts'

export default defineConfig({
  plugins: [react(), tailwindcss(), {
    name: 'product-name',
    transformIndexHtml: html => html.replaceAll('%PRODUCT_NAME%', PRODUCT_NAME),
  }],
})
