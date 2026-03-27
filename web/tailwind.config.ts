import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "#0f172a",
        panel: "#1e293b",
        accent: "#22c55e",
      },
    },
  },
  plugins: [],
};

export default config;
