import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0A0E1A",
        surface: "#111827",
        card: "#1a2235",
        borderc: "rgba(99,102,241,0.2)",
        indigo: { DEFAULT: "#6366F1", light: "#818CF8" },
        cyan: "#06B6D4",
        emerald: "#10B981",
        amber: "#F59E0B",
        rose: "#F43F5E",
        muted: "#94A3B8",
        // --- Admin / DNA monitoring dashboard palette (dark-only) ---
        admin: {
          bg: "#0A0A0F",
          surface: "#12121A",
          elevated: "#171722",
          border: "#1E1E2E",
          primary: "#6C63FF",
          "primary-soft": "rgba(108,99,255,0.15)",
          success: "#00D68F",
          warning: "#FFB300",
          error: "#FF4757",
          info: "#3B9EFF",
          txt: "#FFFFFF",
          sub: "#8B8BA7",
        },
      },
      keyframes: {
        "pulse-ring": {
          "0%": { boxShadow: "0 0 0 0 rgba(0,214,143,0.45)" },
          "70%": { boxShadow: "0 0 0 6px rgba(0,214,143,0)" },
          "100%": { boxShadow: "0 0 0 0 rgba(0,214,143,0)" },
        },
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
      },
      animation: {
        "pulse-ring": "pulse-ring 2s infinite",
        shimmer: "shimmer 1.5s infinite",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
