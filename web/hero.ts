import { heroui } from "@heroui/react";

// Acento "Garmin blue" consistente nas duas variantes de tema — usado pela tab
// ativa, botoes primarios, progress bars e links em todo o app.
export default heroui({
  themes: {
    light: {
      colors: {
        primary: {
          DEFAULT: "#0d6eb8",
          foreground: "#ffffff",
        },
        focus: "#0d6eb8",
      },
    },
    dark: {
      colors: {
        primary: {
          DEFAULT: "#4da3ff",
          foreground: "#04121f",
        },
        focus: "#4da3ff",
      },
    },
  },
});
