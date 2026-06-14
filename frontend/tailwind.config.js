/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#fff1f1",
          100: "#ffe0e0",
          500: "#ff0000",
          600: "#e00000",
          700: "#c00000",
        },
      },
    },
  },
  plugins: [],
};
