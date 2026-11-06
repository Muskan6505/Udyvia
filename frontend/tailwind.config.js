/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: { DEFAULT: "#1E2A78", deep: "#141C55", soft: "#4C58A8", wash: "#E7EAF8" },
        paper: { DEFAULT: "#F5F6FB", warm: "#FFFFFF" },
        haldi: { DEFAULT: "#F2B705", deep: "#B88700", wash: "#FFF4CC" },
        chilli: { DEFAULT: "#D6342C", wash: "#FDE8E6" },
        leaf: { DEFAULT: "#1F8A57", wash: "#E2F4EA" },
        slate2: "#5B6075",
      },
      fontFamily: {
        display: ['"Bricolage Grotesque"', "Hind", "system-ui", "sans-serif"],
        body: ["Hind", '"Noto Sans Devanagari"', "system-ui", "sans-serif"],
      },
      boxShadow: { slip: "0 1px 0 rgba(30,42,120,.08), 0 18px 40px -18px rgba(30,42,120,.35)" },
    },
  },
  plugins: [],
};
