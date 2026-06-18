import path from "path"
import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    // Em dev (npm run dev), encaminha a API pro FastAPI em :8000 (mesma origem p/ cookie).
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
})
