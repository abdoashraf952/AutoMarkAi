import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./hooks/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Deep space canvas
        ink: {
          950: "#05060f",
          900: "#0a0c1b",
          800: "#11142b",
          700: "#1a1e3a",
        },
        // Neon accent system
        accent: {
          DEFAULT: "#7c5cff",
          violet: "#7c5cff",
          cyan: "#22d3ee",
          pink: "#ff5cc8",
          lime: "#a3e635",
        },
        glass: {
          DEFAULT: "rgba(255,255,255,0.06)",
          strong: "rgba(255,255,255,0.10)",
          border: "rgba(255,255,255,0.12)",
        },
      },
      fontFamily: {
        sans: ["var(--font-geist)", "system-ui", "sans-serif"],
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(124,92,255,0.25), 0 8px 40px -8px rgba(124,92,255,0.45)",
        "glow-cyan": "0 0 0 1px rgba(34,211,238,0.25), 0 8px 40px -8px rgba(34,211,238,0.45)",
        card: "0 10px 50px -12px rgba(0,0,0,0.6)",
      },
      backdropBlur: {
        xl: "24px",
      },
      keyframes: {
        "aurora-1": {
          "0%, 100%": { transform: "translate(0,0) scale(1)" },
          "33%": { transform: "translate(8%, -6%) scale(1.15)" },
          "66%": { transform: "translate(-6%, 8%) scale(0.95)" },
        },
        "aurora-2": {
          "0%, 100%": { transform: "translate(0,0) scale(1)" },
          "33%": { transform: "translate(-10%, 6%) scale(1.1)" },
          "66%": { transform: "translate(6%, -8%) scale(1.05)" },
        },
        "rise": {
          "0%": { opacity: "0", transform: "translateY(14px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "shimmer": {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        "pulse-ring": {
          "0%": { transform: "scale(0.8)", opacity: "0.7" },
          "100%": { transform: "scale(2.2)", opacity: "0" },
        },
        "spin-slow": {
          to: { transform: "rotate(360deg)" },
        },
        "float": {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-8px)" },
        },
      },
      animation: {
        "aurora-1": "aurora-1 18s ease-in-out infinite",
        "aurora-2": "aurora-2 22s ease-in-out infinite",
        rise: "rise 0.5s cubic-bezier(0.22,1,0.36,1) both",
        shimmer: "shimmer 2.2s linear infinite",
        "pulse-ring": "pulse-ring 1.8s cubic-bezier(0.22,1,0.36,1) infinite",
        "spin-slow": "spin-slow 8s linear infinite",
        float: "float 4s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;
