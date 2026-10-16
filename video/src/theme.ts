import { loadFont as loadInter } from "@remotion/google-fonts/Inter";
import { loadFont as loadMono } from "@remotion/google-fonts/JetBrainsMono";

export const inter = loadInter("normal", { weights: ["400", "500", "600", "700", "800"], subsets: ["latin"] }).fontFamily;
export const mono = loadMono("normal", { weights: ["400", "500"], subsets: ["latin"] }).fontFamily;

export const C = {
  bg: "#0b0d12",
  panel: "#12151c",
  panel2: "#171b24",
  line: "#232836",
  text: "#e6e8ee",
  dim: "#8a90a2",
  blue: "#5b8cff",
  green: "#2fbf71",
  red: "#ef5a5a",
  amber: "#f2b33d",
  purple: "#a57bff",
};

export const FPS = 30;
