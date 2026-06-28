import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#0b0e11",
        surface: "#161a20",
        surface2: "#1e2329",
        border: "#2b3139",
        text: "#eaecef",
        muted: "#8a929e",
        accent: "#fcd535",
        accentHover: "#f0b90b",
        positive: "#0ecb81",
        negative: "#f6465d",
        warning: "#f59e0b",
        info: "#3b82f6"
      },
      fontFamily: {
        sans: ["IBM Plex Sans", "Inter", "system-ui", "sans-serif"],
        mono: ["IBM Plex Mono", "monospace"]
      },
      boxShadow: {
        panel: "0 0 0 1px rgba(43,49,57,.9)"
      }
    }
  },
  plugins: []
};

export default config;

