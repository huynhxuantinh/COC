/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#090b10",
          900: "#0f131b",
          850: "#151a24",
          800: "#1b2230",
          700: "#293243",
        },
        cobalt: "#38bdf8",
        limewash: "#a3e635",
        danger: "#f43f5e",
        warning: "#f59e0b",
      },
      boxShadow: {
        panel: "0 18px 60px rgba(0,0,0,0.28)",
      },
    },
  },
  plugins: [],
};
