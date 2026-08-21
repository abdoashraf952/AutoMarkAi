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
        // Warm luxury dark canvas — evokes premium materials: aged wood, dark marble
        ink: {
          950: "#0A0805",  // warm near-black
          900: "#110E08",  // dark warm brown
          800: "#1C1610",  // medium warm dark
          700: "#281E0E",  // lighter warm dark
        },
        // Luxury real estate accent system:
        // gold (prestige primary) → sand (bright secondary) → amber (depth)
        accent: {
          DEFAULT: "#C9A84C",
          violet: "#C9A84C",   // gold — primary prestige
          cyan: "#E8C97A",     // sand gold — bright secondary
          pink: "#D97706",     // amber — warm depth accent
          lime: "#34d399",     // emerald — "online" / success (preserved)
          amber: "#FEF3C7",    // cream — recommended highlight
        },
        glass: {
          DEFAULT: "rgba(255,255,255,0.06)",
          strong: "rgba(255,255,255,0.10)",
          border: "rgba(255,255,255,0.12)",
        },
      },
      fontFamily: {
        sans: ["var(--font-geist)", "system-ui", "sans-serif"],
        serif: ["Playfair Display", "Georgia", "Times New Roman", "serif"],
      },
      boxShadow: {
        glow:       "0 0 0 1px rgba(201,168,76,0.25), 0 8px 40px -8px rgba(201,168,76,0.45)",
        "glow-cyan":"0 0 0 1px rgba(232,201,122,0.25), 0 8px 40px -8px rgba(232,201,122,0.45)",
        "glow-amber":"0 0 0 1px rgba(217,119,6,0.35), 0 10px 40px -10px rgba(217,119,6,0.5)",
        card:       "0 10px 50px -12px rgba(0,0,0,0.55)",
      },
      backdropBlur: {
        xl: "24px",
      },
      keyframes: {
        "aurora-1": {
          "0%, 100%": { transform: "translate(0,0) scale(1)" },
          "33%":      { transform: "translate(8%, -6%) scale(1.15)" },
          "66%":      { transform: "translate(-6%, 8%) scale(0.95)" },
        },
        "aurora-2": {
          "0%, 100%": { transform: "translate(0,0) scale(1)" },
          "33%":      { transform: "translate(-10%, 6%) scale(1.1)" },
          "66%":      { transform: "translate(6%, -8%) scale(1.05)" },
        },
        "rise": {
          "0%":   { opacity: "0", transform: "translateY(14px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "shimmer": {
          "0%":   { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        "pulse-ring": {
          "0%":   { transform: "scale(0.8)", opacity: "0.7" },
          "100%": { transform: "scale(2.2)", opacity: "0" },
        },
        "spin-slow": {
          to: { transform: "rotate(360deg)" },
        },
        "float": {
          "0%, 100%": { transform: "translateY(0)" },
          "50%":      { transform: "translateY(-8px)" },
        },
        "float-slow": {
          "0%, 100%": { transform: "translateY(0) rotate(0deg)" },
          "50%":      { transform: "translateY(-10px) rotate(0.8deg)" },
        },
        "float-alt": {
          "0%, 100%": { transform: "translateY(-5px) rotate(0deg)" },
          "50%":      { transform: "translateY(5px) rotate(-0.8deg)" },
        },
      },
      animation: {
        "aurora-1":    "aurora-1 18s ease-in-out infinite",
        "aurora-2":    "aurora-2 22s ease-in-out infinite",
        rise:          "rise 0.5s cubic-bezier(0.22,1,0.36,1) both",
        shimmer:       "shimmer 2.2s linear infinite",
        "pulse-ring":  "pulse-ring 1.8s cubic-bezier(0.22,1,0.36,1) infinite",
        "spin-slow":   "spin-slow 8s linear infinite",
        float:         "float 4s ease-in-out infinite",
        "float-slow":  "float-slow 6s ease-in-out infinite",
        "float-alt":   "float-alt 5s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;
