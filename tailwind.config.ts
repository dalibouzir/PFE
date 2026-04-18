import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: "#007E2F",
          hover: "#006C28",
          light: "#E7F3EC",
        },
        secondary: {
          DEFAULT: "#4FA3C7",
          light: "#EAF5FB",
        },
        semantic: {
          success: "#007E2F",
          warning: "#D4A017",
          danger: "#D64545",
          info: "#2F80ED",
          ai: "#7B61FF",
        },
        neutral: {
          bg: "#F5F1E8",
          surface: "#FFFDF7",
          soft: "#F8F4EA",
          border: "#E4DCCF",
          text: "#1F2A24",
          muted: "#6E6759",
        },
      },
    },
  },
  plugins: [],
};

export default config;
