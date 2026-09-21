/**
 * ===================================================================================
 * NEXI BUS - HIGH-RELIABILITY MESSAGE BUS & EVENT BROKER
 * ===================================================================================
 * Proporciona un canal de mensajería asíncrono, bidireccional y tolerante a fallos
 * entre el Orquestador central (Broker) y los personajes (iframes / componentes).
 * 
 * Características clave:
 *  - Confirmaciones obligatorias (ACK/NACK)
 *  - Cola de mensajes pendientes hasta que el destinatario envíe handshake (READY)
 *  - Reintentos automáticos con timeout por mensaje
 *  - Registro de auditoría circular para telemetría y depuración
 *  - Compatible con arquitectura multi-iframe y componentes embebidos
 * ===================================================================================
 */

(function (global) {
    'use strict';

    const MSG_TYPE = 'NEXI_BUS_MSG';
    const ACK_TYPE = 'NEXI_BUS_ACK';
    const HANDSHAKE_TYPE = 'NEXI_BUS_HANDSHAKE';

    const DEFAULT_TIMEOUT_MS = 600;
    const DEFAULT_MAX_RETRIES = 3;
    const LOG_CAPACITY = 100;

    class NexiBus {
        /**
         * @param {string} clientId - Identificador único de este actor (ej. 'orchester', 'sphere', 'config-panel')
         * @param {object} [options]
         * @param {boolean} [options.isBroker=false] - Si este nodo actúa como router central
         * @param {boolean} [options.debug=false] - Si imprime logs detallados en consola
         */
        constructor(clientId, options = {}) {
            this.clientId = clientId;
            this.isBroker = options.isBroker || false;
            this.debug = options.debug !== undefined ? options.debug : true;

            this.handlers = new Map(); // action -> Set of callbacks
            this.pendingAcks = new Map(); // msgId -> { resolve, reject, timer, message, retriesLeft, timeoutMs }
            this.clients = new Map(); // clientId -> window reference (solo broker)
            this.deliveryQueue = new Map(); // clientId -> Array<message> (mensajes retenidos antes de READY)
            this.readyClients = new Set(); // Conjunto de clientes que ya completaron handshake
            
            this.eventLog = []; // Búfer circular de auditoría

            this._onMessageReceived = this._onMessageReceived.bind(this);
            window.addEventListener('message', this._onMessageReceived);

            this._log('INIT', `NexiBus inicializado para [${this.clientId}] (isBroker: ${this.isBroker})`);

            // Si es un cliente, saludar al broker de inmediato
            if (!this.isBroker && window.parent && window.parent !== window) {
                this.sendHandshake();
            }
        }

        // =========================================================================
        // REGISTRO DE EVENTOS Y LOGS
        // =========================================================================

        _log(level, text, details = null) {
            const entry = {
                time: new Date().toISOString().substring(11, 23),
                level,
                text,
                details
            };
            this.eventLog.push(entry);
            if (this.eventLog.length > LOG_CAPACITY) {
                this.eventLog.shift();
            }
            if (this.debug) {
                const color = level === 'ERROR' ? '#ff4d4d' : level === 'ACK' ? '#00ff88' : '#00d5ff';
                console.log(`%c[NexiBus:${this.clientId}][${entry.time}][${level}] ${text}`, `color: ${color}; font-weight: bold;`, details || '');
            }
        }

        getLog() {
            return [...this.eventLog];
        }

        setDebug(enabled) {
            this.debug = !!enabled;
        }

        // =========================================================================
        // HANDSHAKE & REGISTRO DE CLIENTES
        // =========================================================================

        sendHandshake() {
            const handshake = {
                type: HANDSHAKE_TYPE,
                sender: this.clientId,
                timestamp: Date.now()
            };
            try {
                window.parent.postMessage(handshake, '*');
                this._log('HANDSHAKE_SENT', `Handshake emitido a broker desde [${this.clientId}]`);
            } catch (err) {
                this._log('ERROR', `Fallo al enviar handshake: ${err.message}`);
            }
        }

        /**
         * Registra un cliente hijo en el broker (usado por el orquestador al crear iframes).
         * @param {string} clientId
         * @param {Window} targetWindow
         */
        registerClient(clientId, targetWindow) {
            if (!this.isBroker) return;
            this.clients.set(clientId, targetWindow);
            this._log('CLIENT_REGISTERED', `Cliente registrado [${clientId}] en broker`);
        }

        markClientReady(clientId, sourceWindow) {
            if (!this.isBroker) return;
            this.clients.set(clientId, sourceWindow);
            this.readyClients.add(clientId);
            this._log('CLIENT_READY', `Handshake recibido: [${clientId}] está LISTO`);

            // Despachar cualquier mensaje retenido en la cola
            if (this.deliveryQueue.has(clientId)) {
                const queue = this.deliveryQueue.get(clientId);
                this.deliveryQueue.delete(clientId);
                this._log('FLUSH_QUEUE', `Despachando ${queue.length} mensaje(s) retenidos para [${clientId}]`);
                queue.forEach(msg => this._dispatchToTarget(msg));
            }
        }

        // =========================================================================
        // SUSCRIPCIÓN A ACCIONES
        // =========================================================================

        /**
         * Registra un manejador para una acción específica.
         * @param {string} action
         * @param {Function} handler - Función que recibe (payload, meta) y puede retornar datos o una Promise.
         */
        on(action, handler) {
            if (!this.handlers.has(action)) {
                this.handlers.set(action, new Set());
            }
            this.handlers.get(action).add(handler);
            return () => this.off(action, handler);
        }

        off(action, handler) {
            if (this.handlers.has(action)) {
                this.handlers.get(action).delete(handler);
            }
        }

        // =========================================================================
        // ENVÍO DE MENSAJES CON PROMESA, TIMEOUT Y REINTENTOS
        // =========================================================================

        /**
         * Envía un mensaje con garantía de entrega y respuesta.
         * @param {string} target - ID del destinatario ('sphere', 'orchester', 'config-panel', etc.)
         * @param {string} action - Nombre del comando o evento (ej. 'SET_PARAM', 'GET_STATE')
         * @param {*} [payload] - Datos a transferir
         * @param {object} [options]
         * @param {number} [options.timeoutMs=600]
         * @param {number} [options.maxRetries=3]
         * @returns {Promise<any>} Resuelve con la respuesta del receptor o rechaza con error
         */
        send(target, action, payload = {}, options = {}) {
            const timeoutMs = options.timeoutMs || DEFAULT_TIMEOUT_MS;
            const maxRetries = options.maxRetries !== undefined ? options.maxRetries : DEFAULT_MAX_RETRIES;
            const msgId = this._generateId();

            const message = {
                type: MSG_TYPE,
                msgId,
                sender: this.clientId,
                target,
                action,
                payload,
                attempt: 1,
                timestamp: Date.now()
            };

            return new Promise((resolve, reject) => {
                const pending = {
                    resolve,
                    reject,
                    message,
                    target,
                    action,
                    timeoutMs,
                    retriesLeft: maxRetries,
                    timer: null
                };

                this.pendingAcks.set(msgId, pending);
                this._startAckTimer(msgId);
                this._dispatch(message);
            });
        }

        _startAckTimer(msgId) {
            const pending = this.pendingAcks.get(msgId);
            if (!pending) return;

            if (pending.timer) {
                clearTimeout(pending.timer);
            }

            pending.timer = setTimeout(() => {
                this._handleTimeout(msgId);
            }, pending.timeoutMs);
        }

        _handleTimeout(msgId) {
            const pending = this.pendingAcks.get(msgId);
            if (!pending) return;

            if (pending.retriesLeft > 0) {
                pending.retriesLeft--;
                pending.message.attempt++;
                this._log('RETRY', `Timeout en msgId [${msgId}] (${pending.action} -> ${pending.target}). Reintentando (${pending.retriesLeft} restantes)...`);
                this._startAckTimer(msgId);
                this._dispatch(pending.message);
            } else {
                this._log('ERROR', `MsgId [${msgId}] agotó todos los reintentos hacia [${pending.target}]. Transacción fallida.`);
                this.pendingAcks.delete(msgId);
                pending.reject(new Error(`Timeout: No se recibió ACK de [${pending.target}] para la acción '${pending.action}' tras múltiples reintentos.`));
            }
        }

        // =========================================================================
        // ENCAMINAMIENTO Y DESPACHO (ROUTING)
        // =========================================================================

        _dispatch(message) {
            // Si este nodo es el broker:
            if (this.isBroker) {
                if (message.target === this.clientId) {
                    // El broker se envía un mensaje a sí mismo
                    this._executeLocalHandlers(message);
                } else {
                    this._dispatchToTarget(message);
                }
            } else {
                // Si es un cliente, todo mensaje sale hacia el broker (window.parent)
                try {
                    window.parent.postMessage(message, '*');
                    this._log('OUT', `[${this.clientId} -> ${message.target}] Acción: '${message.action}' (msgId: ${message.msgId})`);
                } catch (err) {
                    this._log('ERROR', `Fallo al despachar hacia broker: ${err.message}`);
                }
            }
        }

        _dispatchToTarget(message) {
            const targetWindow = this.clients.get(message.target);

            // Si el target aún no está listo y no es un ACK, lo encolamos
            if (!this.readyClients.has(message.target) && message.type === MSG_TYPE) {
                this._log('QUEUE', `Destinatario [${message.target}] no listo. Encolando msgId [${message.msgId}]`);
                if (!this.deliveryQueue.has(message.target)) {
                    this.deliveryQueue.set(message.target, []);
                }
                this.deliveryQueue.get(message.target).push(message);
                return;
            }

            if (targetWindow && !targetWindow.closed) {
                try {
                    targetWindow.postMessage(message, '*');
                    this._log('ROUTED', `Broker enrutó a [${message.target}] la acción '${message.action || 'ACK'}'`);
                } catch (err) {
                    this._log('ERROR', `Error al enviar a cliente [${message.target}]: ${err.message}`);
                }
            } else {
                this._log('WARN', `Destinatario [${message.target}] no encontrado o cerrado en broker`);
            }
        }

        // =========================================================================
        // RECEPCIÓN Y MANEJO DE MENSAJES
        // =========================================================================

        _onMessageReceived(event) {
            const data = event.data;
            if (!data || typeof data !== 'object' || !data.type) return;

            // 1. MANEJO DE HANDSHAKE (Solo en Broker)
            if (data.type === HANDSHAKE_TYPE) {
                if (this.isBroker) {
                    this.markClientReady(data.sender, event.source);
                    // Responder con ACK de handshake al cliente
                    try {
                        event.source.postMessage({
                            type: ACK_TYPE,
                            msgId: 'handshake',
                            sender: this.clientId,
                            target: data.sender,
                            status: 'OK',
                            data: { brokerReady: true }
                        }, '*');
                    } catch (e) {}
                }
                return;
            }

            // 2. MANEJO DE ACK / NACK
            if (data.type === ACK_TYPE) {
                // Si este nodo es el destinatario del ACK:
                if (data.target === this.clientId) {
                    this._handleAck(data);
                } else if (this.isBroker) {
                    // El broker enruta el ACK hacia el remitente original
                    this._dispatchToTarget(data);
                }
                return;
            }

            // 3. MANEJO DE MENSAJE REGULAR (NEXI_BUS_MSG)
            if (data.type === MSG_TYPE) {
                // Si es para este nodo:
                if (data.target === this.clientId || data.target === '*') {
                    this._executeLocalHandlers(data, event.source);
                } else if (this.isBroker) {
                    // El broker lo enruta al destinatario final
                    this._dispatchToTarget(data);
                }
            }
        }

        _handleAck(ackData) {
            const pending = this.pendingAcks.get(ackData.msgId);
            if (!pending) return;

            clearTimeout(pending.timer);
            this.pendingAcks.delete(ackData.msgId);

            if (ackData.status === 'OK') {
                this._log('ACK', `ACK recibido de [${ackData.sender}] para msgId [${ackData.msgId}]`);
                pending.resolve(ackData.data);
            } else {
                this._log('NACK', `NACK recibido de [${ackData.sender}] para msgId [${ackData.msgId}]: ${ackData.error}`);
                pending.reject(new Error(ackData.error || 'NACK: Error devuelto por receptor'));
            }
        }

        async _executeLocalHandlers(message, sourceWindow) {
            this._log('IN', `Mensaje recibido de [${message.sender}]: '${message.action}'`, message.payload);

            const actionHandlers = this.handlers.get(message.action);
            let responseData = null;
            let executionError = null;

            if (actionHandlers && actionHandlers.size > 0) {
                try {
                    // Ejecutar todos los handlers registrados para esta acción
                    for (const handler of actionHandlers) {
                        responseData = await handler(message.payload, {
                            sender: message.sender,
                            msgId: message.msgId,
                            timestamp: message.timestamp
                        });
                    }
                } catch (err) {
                    executionError = err.message || String(err);
                }
            } else {
                this._log('WARN', `Sin manejador registrado para la acción '${message.action}'`);
            }

            // Devolver ACK obligatorio al emisor
            const ack = {
                type: ACK_TYPE,
                msgId: message.msgId,
                sender: this.clientId,
                target: message.sender,
                status: executionError ? 'ERROR' : 'OK',
                error: executionError,
                data: responseData,
                timestamp: Date.now()
            };

            if (this.isBroker) {
                if (message.sender === this.clientId) {
                    this._handleAck(ack);
                } else {
                    this._dispatchToTarget(ack);
                }
            } else if (sourceWindow || window.parent) {
                const targetWin = sourceWindow || window.parent;
                try {
                    targetWin.postMessage(ack, '*');
                } catch (e) {
                    this._log('ERROR', `Fallo al devolver ACK: ${e.message}`);
                }
            }
        }

        _generateId() {
            if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
                return crypto.randomUUID();
            }
            return 'msg_' + Date.now() + '_' + Math.random().toString(36).substring(2, 9);
        }
    }

    // Exposición global
    global.NexiBus = NexiBus;

})(typeof window !== 'undefined' ? window : this);
