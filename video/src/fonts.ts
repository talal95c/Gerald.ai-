import { loadFont } from "@remotion/fonts";
import { staticFile } from "remotion";

export const fontsReady = Promise.all([
  loadFont({ family: "Google Sans Flex", url: staticFile("fonts/GoogleSansFlex.ttf"), weight: "100 1000" }),
  loadFont({ family: "Geist", url: staticFile("fonts/Geist.woff2"), weight: "100 900" }),
  loadFont({ family: "Abel", url: staticFile("fonts/Abel-Regular.ttf"), weight: "400" }),
  loadFont({ family: "Caveat", url: staticFile("fonts/Caveat-SemiBold.ttf"), weight: "600" }),
]);
