// Obtener el botón
const button = document.getElementById('load-btn');

// Cargar solo cuando se haga clic
window.onload = () => {
    button.textContent = 'Cargar archivo';
};

// Función principal para cargar logs
function loadLogs() {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '';

    // === 🔁 MOSTRAR LOADER Y OCULTAR MENSAJE INICIAL ===
    const initialMessage = document.getElementById('initial-message');
    const loadingIndicator = document.getElementById('loading-indicator');

    if (initialMessage) initialMessage.style.display = 'none';
    if (loadingIndicator) loadingIndicator.style.display = 'flex';

    // === 🔇 OCULTAR FILTROS Y TABLA AL INICIAR ===
    const systemContainer = document.getElementById("system-meta");
    const filterContainer = document.getElementById("filters-wrapper-main");
    const tableContainer = document.getElementById("table-container-main");

    if(systemContainer){
        systemContainer.style.display = "none";
    }
    if (filterContainer) {
        filterContainer.style.visibility = "hidden";
    }
    if (tableContainer) {
        tableContainer.style.visibility = "hidden";
    }

    input.onchange = function (e) {
        const file = e.target.files[0];
        if (!file) {
            // Si se cancela, restaurar mensaje
            if (loadingIndicator) loadingIndicator.style.display = 'none';
            if (initialMessage) initialMessage.style.display = 'block';
            return;
        }

        // Validar extensión
        if (!file.name.endsWith('.logs') && !file.name.startsWith('.logs')) {
            alert('Por favor, selecciona un archivo con extensión .logs');
            if (loadingIndicator) loadingIndicator.style.display = 'none';
            if (initialMessage) initialMessage.style.display = 'block';
            return;
        }

        const reader = new FileReader();
        reader.onload = function (event) {
            const text = event.target.result;
            parseAndDisplayLogs(text);
            button.textContent = '↻ Recargar';

            // === ✅ MOSTRAR FILTROS Y TABLA AL FINAL ===
            if (filterContainer) {
                filterContainer.style.visibility = "visible";
            }
            if (tableContainer) {
                tableContainer.style.visibility = "visible";
            }

            // === ✅ OCULTAR LOADER ===
            if (loadingIndicator) loadingIndicator.style.display = 'none';
        };

        // ✅ Manejar errores de lectura
        reader.onerror = function () {
            alert('Error al leer el archivo.');
            if (loadingIndicator) loadingIndicator.style.display = 'none';
            if (initialMessage) initialMessage.style.display = 'block';
        };

        reader.readAsText(file);
    };

    input.click();
}

// --- EVENTO DEL BOTÓN ---
button.addEventListener('click', (e) => {
    e.preventDefault();
    loadLogs();
});

// --- PARSEO Y MUESTRA DE LOGS ---
function parseAndDisplayLogs(text) {
    const logsContainer = document.getElementById('logs');
    const metaGrid = document.getElementById('meta-grid');
    const systemMeta = document.getElementById('system-meta');

    if (!logsContainer) {
        console.error('❌ No se encontró el elemento #logs');
        return;
    }

    logsContainer.innerHTML = '';
    if (metaGrid) metaGrid.innerHTML = '';
    if (systemMeta) systemMeta.style.display = 'none';

    let metaParsed = false;

    // === 🔧 SIEMPRE AÑADIR \n AL FINAL (en memoria) ===
    const normalizedText = text + '\n.';

    // Dividir por líneas
    const lines = normalizedText
        .replace(/\r\n/g, '\n')
        .replace(/\r/g, '\n')
        .split('\n');

    // Contador de logs
    let logCount = 0;

    // === 🎨 LEER VARIABLES DE CSS ===
    const rootStyle = getComputedStyle(document.documentElement);

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];

        // ✅ Verificar si está vacía o solo tiene espacios
        if (!line.trim()) continue;

        // Parsear META
        if (line.trim().startsWith('##META:') && !metaParsed && metaGrid && systemMeta) {
            try {
                const meta = JSON.parse(line.trim().replace('##META:', '').trim());
                for (let [key, value] of Object.entries(meta)) {
                    const item = document.createElement('div');
                    item.className = 'meta-item';
                    const label = key.charAt(0).toUpperCase() + key.slice(1);
                    item.innerHTML = `
                        <span class="meta-label">${label}:&nbsp;</span>
                        <span class="meta-value">${escapeHtml(value || '-')}</span>
                    `;
                    metaGrid.appendChild(item);
                }
                systemMeta.style.display = 'block';
                metaParsed = true;
            } catch (e) {
                console.warn('META inválido:', e);
            }
            continue;
        }

        // Parsear log
        const parts = line.split(',').map(part => part.trim());
        if (parts.length < 6) continue; // Necesitamos al menos: sid, type, timestamp, user, location, message

        const [sid, typeRaw, timestamp, user, location, ...messageParts] = parts;
        const message = messageParts.join(', ').trim();

        const typeMatch = typeRaw.match(/\[(INFO|ERROR|ALERT|NOTE)\]/i);
        const type = typeMatch ? typeMatch[1].toUpperCase() : 'NOTE';

        const safeTypeRaw = typeRaw || '-';
        const safeTimestamp = timestamp || '-';
        const safeLocation = location || '-';
        const safeMessage = message || '-';
        let safeUser = user ? user : 'unregistered';
        const isRegistered = !!user;

        safeUser = safeUser.replace("by","");
        // Incrementar contador
        logCount++;

        // Crear fila
        const tr = document.createElement('tr');
        tr.className = `entry ${type}`;
        tr.dataset.type = type;
        tr.dataset.search = [sid, safeTypeRaw, safeTimestamp, safeUser, safeLocation, safeMessage]
            .join(' ')
            .toLowerCase();

        // === 🎨 APLICAR COLOR DE FONDO POR SESIÓN ===
        tr.style.backgroundColor = colorear(sid, rootStyle);

        // Rellenar con ceros: 1 → 00001
        const paddedCount = logCount.toString().padStart(5, '0');

        tr.innerHTML = `
            <td class="num">${paddedCount}</td>
            <td class="sid">${escapeHtml(sid)}</td>
            <td class="type-cell type-${type.toLowerCase()}">${escapeHtml(safeTypeRaw)}</td>
            <td class="timestamp">${escapeHtml(safeTimestamp)}</td>
            <td class="name ${isRegistered ? '' : 'unregistered'}">${escapeHtml(safeUser)}</td>
            <td class="file">${escapeHtml(safeLocation)}</td>
            <td class="message">${escapeHtml(safeMessage)}</td>
        `;

        logsContainer.appendChild(tr);
    }

    // Aplicar filtros
    filterLogs();
}

// --- FUNCIONES DE APOYO ---
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// --- FILTROS (búsqueda y checkboxes) ---
function filterLogs() {
    const searchInput = document.getElementById('search-input');
    const searchTerm = searchInput ? searchInput.value.trim().toLowerCase() : '';

    const checkboxes = document.querySelectorAll('.filter-tag input[type="checkbox"]');
    const selectedTypes = Array.from(checkboxes)
        .filter(cb => cb.checked)
        .map(cb => cb.value);

    const rows = document.querySelectorAll('#logs tr.entry');

    rows.forEach(row => {
        const type = row.dataset.type;
        const cells = row.querySelectorAll('td');

        // Verificar si el tipo está seleccionado
        const matchesType = selectedTypes.includes(type);

        // Si no coincide con el tipo, ocultar
        if (!matchesType) {
            row.style.display = 'none';
            return;
        }

        // Si no hay término de búsqueda, mostrar
        if (!searchTerm) {
            row.style.display = '';
            return;
        }

        // Buscar en el texto de todas las celdas
        let matchesSearch = false;
        for (let cell of cells) {
            if (cell.textContent.toLowerCase().includes(searchTerm)) {
                matchesSearch = true;
                break;
            }
        }

        row.style.display = matchesSearch ? '' : 'none';
    });
}

// --- EVENTOS DE FILTROS ---
document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.getElementById('search-input');
    if (searchInput) {
        searchInput.addEventListener('input', filterLogs);
    }

    document.querySelectorAll('.filter-tag input[type="checkbox"]').forEach(checkbox => {
        checkbox.addEventListener('change', filterLogs);
    });
});

// === 🎨 FUNCION PARA COLOREAR POR SESIÓN ===
function colorear(sid, rootStyle) {
    // Usamos un mapa para asignar cada sID a un índice (0 o 1)
    if (!colorear.map) {
        colorear.map = new Map();
        colorear.counter = 0;
    }

    if (!colorear.map.has(sid)) {
        colorear.map.set(sid, colorear.counter % 2);
        colorear.counter++;
    }

    const index = colorear.map.get(sid);
    return index === 0
        ? rootStyle.getPropertyValue('--row-bg').trim()
        : rootStyle.getPropertyValue('--row-bg-alt').trim();
}