import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Anthropic-portal-inspired warm light palette.
        bg: "#F5F3EE", // ivory page background
        ink: "#F1EFE7", // soft inset / field surface
        panel: "#FFFFFF", // card surface
        panel2: "#EEEBE1", // subtle surface (buttons, active tab)
        line: "#E4E0D4", // warm hairline border
        head: "#1A1915", // near-black warm heading/text
        accent: "#CC785C", // Anthropic clay / coral
        accent2: "#B5634A", // deeper clay (primary buttons)
        ok: "#3E8E62",
        warn: "#9A6B1E",
        danger: "#B5483A",
        muted: "#6E6B61",
      },
      fontFamily: {
        sans: ["var(--font-sans)", "ui-sans-serif", "system-ui", "Segoe UI", "sans-serif"],
        serif: ["ui-serif", "Georgia", "Cambria", "Times New Roman", "serif"],
      },
      boxShadow: {
        soft: "0 1px 2px rgba(26,25,21,0.04), 0 4px 16px rgba(26,25,21,0.05)",
      },
    },
  },
  plugins: [],
};

export default config;
