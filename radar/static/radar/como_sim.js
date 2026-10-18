import { iniciarSim } from "./simulacion.js";
iniciarSim(document.getElementById("sim-vivo"), JSON.parse(document.getElementById("datos-vivo").textContent));
