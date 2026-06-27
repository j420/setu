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
        ink: "#0b0e1a",
        panel: "#141831",
        panel2: "#1b2040",
        line: "#2a3052",
        accent: "#5566ee",
        accent2: "#3447c9",
        ok: "#5fe39a",
        warn: "#f3d27a",
        danger: "#f37aa0",
        muted: "#8b93c0",
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
