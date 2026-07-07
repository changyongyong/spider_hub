/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{vue,js}"],
  theme: {
    extend: {
      colors: {
        canvas: "#f5f7fa",
        ink: "#17202a",
        muted: "#667085",
        line: "#d9dee7",
        brand: {
          DEFAULT: "#0f766e",
          strong: "#115e59",
          soft: "#e6fffb"
        }
      },
      boxShadow: {
        panel: "0 1px 2px rgba(16, 24, 40, 0.06)"
      }
    }
  },
  plugins: []
};
