/**
 * ===================================================================================
 * MASK ENGINE - DATA HELPER
 * ===================================================================================
 * Este script define las escenas estáticas y proporciona una función para
 * calcular dinámicamente los datos de los personajes a partir del DOM.
 * ===================================================================================
 */

/**
 * ===================================================================================
 * NOTA DE ARQUITECTURA SOBRE GEOMETRÍA
 * ===================================================================================
 * La estrategia actual para la expansión de máscaras se realiza en JavaScript
 * mediante una expansión matemática simple del 'bounding box' (rectángulo delimitador)
 * de cada elemento.
 *
 * (+) VENTAJA: Es extremadamente rápido y eficiente para formas geométricas simples
 * (círculos, rectángulos), lo cual está alineado con la prioridad del proyecto de
 * "rendimiento sobre diseño".
 *
 * (-) LIMITACIÓN: Este método es una aproximación y no funcionaría para formas
 * complejas o cóncavas (ej. una estrella).
 *
 * FUTURO: Si se necesitaran personajes con formas complejas, la estrategia podría
 * evolucionar para utilizar SVG. El frontend enviaría la descripción del path SVG
 * y el backend de Python se encargaría de interpretar y generar la máscara precisa.
 * ===================================================================================
 */

// Píxeles a expandir en la silueta de cada personaje.
const DILATION_PIXELS = 3;

// Definiciones de escenas.
const SCENE_DEFINITIONS = {
  "0": { sc: 'fullscreen', orchest: [0] },
  "1": { sc: 'nexi-normal', orchest: [0, 1, 2] },          // Esfera + Botón Arrastre exterior
  "2": { sc: 'nexi-menu-open', orchest: [0, 1, 2, 3] },     // Esfera + Botón Arrastre + Menú Contextual
  "3": { sc: 'nexi-config-open', orchest: [0, 1, 2, 4] }    // Esfera + Botón Arrastre + Panel Configuración
};

/**
 * Devuelve la escena inicial que se desea mostrar por defecto.
 * NOTA: No se refiere a la primera escena del objeto (que es '0', el fondo),
 * sino a la primera escena con contenido visible que queremos mostrar al inicio.
 *
 * @returns {string} El ID de la primera escena a mostrar.
 */
function get_first_scene() {
  return "1"; // Se establece '1' como la primera escena visible por defecto.
}

/**
 * LÓGICA CENTRAL: Construye el objeto de datos inicial.
 * @param {string} containerId - El ID del contenedor de personajes.
 * @returns {object} Un objeto con dos claves: 'characters' y 'scenes'.
 */
function get_scenes_and_characters(containerId) {
  const container = document.getElementById(containerId);
  const characterData = {};

  if (container) {
    const elements = container.querySelectorAll(':scope > [id]');
    let characterCounter = 1;

    elements.forEach(element => {
      const rect = element.getBoundingClientRect();
      const computedStyle = window.getComputedStyle(element);

      // Se crea un "clon" de la geometría en memoria y se expande.
      const expanded_geometry = {
          x: rect.x - DILATION_PIXELS,
          y: rect.y - DILATION_PIXELS,
          width: rect.width + (DILATION_PIXELS * 2),
          height: rect.height + (DILATION_PIXELS * 2)
      };

      characterData[element.id] = {
        ch: characterCounter,
        id: crypto.randomUUID(),
        geometry: expanded_geometry, // Se usa la geometría expandida.
        shape: {
          borderRadius: computedStyle.borderRadius
        }
      };
      characterCounter++;
    });
  } else {
    console.warn(`Advertencia: Contenedor con id '${containerId}' no encontrado.`);
  }

  return {
    characters: characterData,
    scenes: SCENE_DEFINITIONS
  };
}