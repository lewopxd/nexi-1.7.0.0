/**
 * ===================================================================================
 * NEXI BRIDGE ENGINE
 * ===================================================================================
 * MODIFICADO: Añadida gestión de estado para el arrastre y nuevas funciones
 * para ser llamadas por los event listeners del orquestador.
 * ===================================================================================
 */

(() => {
    'use strict';

    const MAX_RETRIES = 10;
    const pending_transactions = {};

    // --- GESTIÓN DE ESTADO ---
    let current_scene_id = null;
    let scene_before_drag = null;

    // (Aquí se podría añadir la lógica de localStorage en el futuro)

    function handle_data_lost(lostPayload) {
        // ... (sin cambios)
        console.error(`🔴 CRÍTICO: Se perdieron los datos para la transacción TIPO '${lostPayload.type}' con ID: ${lostPayload.id}.`);
        console.error("🔴 Payload perdido:", lostPayload);
    }

    function send_update_request(attempt = 1) {
        // ... (sin cambios)
        console.log(`JS -> PY: Preparando 'update' (Intento ${attempt}/${MAX_RETRIES})...`);
        const freshData = get_scenes_and_characters('nexi-scene-container');
        const payload = { type: "update", id: crypto.randomUUID(), msg: freshData };
        pending_transactions[payload.id] = { payload: payload, attempt_number: attempt };
        window.py_bridge.receive_message(JSON.stringify(payload));
        console.log(`JS -> PY: Enviando 'update' con nuevo ID: ${payload.id}`);
    }

    function send_change_request(scene_id, attempt = 1) {
        console.log(`JS -> PY: Preparando 'change' (Intento ${attempt}/${MAX_RETRIES})...`);
        if (scene_id === null) {
            console.error("No se puede enviar 'change' sin un ID de escena.");
            return;
        }
        const payload = { type: "change", id: crypto.randomUUID(), sc: scene_id };
        pending_transactions[payload.id] = { payload: payload, attempt_number: attempt };
        window.py_bridge.receive_message(JSON.stringify(payload));
        console.log(`JS -> PY: Enviando 'change' con nuevo ID: ${payload.id} para escena '${scene_id}'`);
    }

    // --- NUEVAS FUNCIONES PARA EL ORQUESTADOR ---

    /**
     * Notifica al sistema que el usuario ha comenzado a arrastrar un elemento.
     */
    function notify_drag_start() {
        console.log("Evento: DRAG START detectado.");
        if (window.py_bridge && typeof window.py_bridge.set_dragging === 'function') {
            window.py_bridge.set_dragging(true);
        }
    }

    /**
     * Notifica al sistema que el usuario ha soltado el elemento.
     */
    function notify_drag_end() {
        console.log("Evento: DRAG END detectado.");
        if (window.py_bridge && typeof window.py_bridge.set_dragging === 'function') {
            window.py_bridge.set_dragging(false);
        }
        // Inicia el proceso de actualización para registrar la nueva posición de hitboxes.
        send_update_request(1);
    }

    // ---------------------------------------------

    function on_python_ready() {
        console.log("JS <- PY: Señal 'on_python_ready' recibida.");
        // Al inicio, la primera escena es la que define get_first_scene()
        const initial_scene = get_first_scene();
        current_scene_id = initial_scene;
        send_update_request(1); // El flujo original de 'update' y luego 'change' sigue aquí.
    }

    function on_update_success(jsonString) {
        const response = JSON.parse(jsonString);
        const received_id = response.id;
        const confirmed_transaction = pending_transactions[received_id];

        if (confirmed_transaction) {
            const type = confirmed_transaction.payload.type;
            console.log(`✅ JS <- PY: Éxito en '${type}' confirmado para ID: ${received_id}`);

            delete pending_transactions[received_id];

            if (type === 'update') {
                const target_scene = current_scene_id || get_first_scene();
                send_change_request(target_scene);
            } else if (type === 'change') {
                // Si el cambio fue exitoso, actualizamos nuestro estado local.
                current_scene_id = confirmed_transaction.payload.sc;
            }
        } else {
            console.error(`🔴 CRÍTICO: Se recibió confirmación para una transacción DESCONOCIDA (ID: ${received_id}).`);
        }
    }

    function on_update_loss(jsonString) {
        // ... (sin cambios)
        const response = JSON.parse(jsonString);
        const failed_id = response.id;
        const failed_transaction = pending_transactions[failed_id];
        if (!failed_transaction) { console.error(`Error: Falla para transacción no registrada (ID: ${failed_id}).`); return; }
        const type = failed_transaction.payload.type;
        const current_attempt = failed_transaction.attempt_number;
        console.warn(`🟡 JS <- PY: Falla en '${type}' reportada para ID: ${failed_id}`);
        delete pending_transactions[failed_id];
        if (current_attempt >= MAX_RETRIES) {
            handle_data_lost(failed_transaction.payload);
        } else {
            console.warn(`Iniciando reintento ${current_attempt + 1} para '${type}'...`);
            if (type === 'update') { send_update_request(current_attempt + 1); }
            else if (type === 'change') { send_change_request(failed_transaction.payload.sc, current_attempt + 1); }
        }
    }

    // Exposición de funciones
    window.on_python_ready = on_python_ready;
    window.on_update_success = on_update_success;
    window.on_update_loss = on_update_loss;
    window.notify_drag_start = notify_drag_start;
    window.notify_drag_end = notify_drag_end;
    window.send_update_request = send_update_request;
    window.send_change_request = send_change_request;

    // Lógica de inicialización
    document.addEventListener('DOMContentLoaded', () => {
        // ... (sin cambios)
        if (typeof qt === 'undefined' || typeof qt.webChannelTransport === 'undefined') { console.error("QWebChannel no encontrado."); return; }
        new QWebChannel(qt.webChannelTransport, (channel) => {
            window.py_bridge = channel.objects.py_bridge;
            console.log("Python bridge conectado.");
            py_bridge.js_ready_signal(true, 'JS Engine conectado y listo.');
        });
    });
})();