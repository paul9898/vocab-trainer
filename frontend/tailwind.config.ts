import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#1a1a1a",
        mist: "#f7f3ea",
        moss: "#1f5d50",
        clay: "#b8643c",
        sunrise: "#f0a04b",
        sea: "#7ab9b5",
      },
      boxShadow: {
        soft: "0 18px 50px rgba(26, 26, 26, 0.08)",
      },
      fontFamily: {
        display: ["Iowan Old Style", "Palatino Linotype", "Book Antiqua", "serif"],
        body: ["Avenir Next", "Segoe UI", "sans-serif"],
      },
    },
  },
  plugins: [],
} satisfies Config;
