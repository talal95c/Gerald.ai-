import { mountNotch } from "./notch";

document.body.classList.add("notch-page");
const root = document.getElementById("root");
if (root) mountNotch(root);
