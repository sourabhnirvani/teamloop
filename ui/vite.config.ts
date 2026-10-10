import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev: `npm run dev` on 5173 talks to the TeamLoop server on 8790. Build: ui/dist, served by the server at /.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { "/api": { target: "http://127.0.0.1:8790", changeOrigin: true } },
  },
});
