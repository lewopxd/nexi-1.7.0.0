# nexi_app/controller/bridge_controller.py
import json
from PySide6.QtCore import QObject, Slot, Signal
from PySide6.QtWebChannel import QWebChannel

from nexi_app.view.main_window import MainWindow
from nexi_app.utils import log

class BridgeController(QObject):
    """
    Actúa como un puente de comunicación entre el frontend (JS) y el backend (Python).
    Su única responsabilidad es recibir, parsear y emitir datos, y enviar respuestas.
    No contiene lógica de aplicación.
    """
    # --- Señales para comunicar eventos al MainController ---
    js_ready = Signal(bool, str)
    update_received = Signal(dict)
    change_received = Signal(dict)

    def __init__(self, view: MainWindow):
        super().__init__()
        self.view = view
        self._setup_web_channel()

    def _setup_web_channel(self):
        """Crea el QWebChannel y registra este objeto como 'py_bridge'."""
        self.channel = QWebChannel(self.view.page())
        self.view.page().setWebChannel(self.channel)
        self.channel.registerObject("py_bridge", self)
        log.info("BridgeController: QWebChannel configurado. Objeto 'py_bridge' registrado.")

    # ==================================================================
    # SLOTS: Puntos de entrada para señales desde JavaScript
    # ==================================================================

    @Slot(bool, str)
    def js_ready_signal(self, success: bool, message: str):
        """Slot que se activa cuando el JS está listo (handshake). Emite una señal local."""
        log.note(f"BRIDGE <- JS: Handshake recibido (success={success}, msg='{message}')")
        self.js_ready.emit(success, message)

    @Slot(bool)
    def set_dragging(self, is_dragging: bool):
        """Slot directo para activar/desactivar modo arrastre instantáneamente sin JSON."""
        log.note(f"BRIDGE <- JS: set_dragging({is_dragging})")
        self.view.set_dragging(is_dragging)

    @Slot(str)
    def receive_message(self, json_string: str):
        """Slot principal para recibir todos los mensajes desde JS. Parsea y emite señales específicas."""
        log.note(f"BRIDGE <- JS: Mensaje JSON crudo recibido: {json_string}")
        request_id = None
        try:
            data = json.loads(json_string)
            request_id = data.get("id")
            msg_type = data.get("type")

            if msg_type == "update":
                self.update_received.emit(data)
            elif msg_type == "change":
                self.change_received.emit(data)
            else:
                log.alert(f"Bridge: Tipo de mensaje no reconocido: {msg_type}")
                self.send_confirmation(request_id, success=False)
        except json.JSONDecodeError as e:
            log.error(f"Bridge: Error al decodificar JSON de JS: {e}", exc_info=True)
            self.send_confirmation(request_id, success=False)

    # ==================================================================
    # MÉTODOS PÚBLICOS: Para enviar datos/confirmaciones a JavaScript
    # ==================================================================

    def send_python_ready_confirmation(self):
        """Envía la confirmación final a JS de que Python está listo."""
        log.note("BRIDGE -> JS: Enviando señal de confirmación 'on_python_ready'.")
        self.view.page().runJavaScript("on_python_ready();")

    def send_confirmation(self, request_id: str, success: bool):
        """Envía una confirmación de vuelta a JS sobre el resultado de una operación."""
        if not request_id: return
        response = {"id": request_id}
        json_response = json.dumps(response).replace("'", "\\'")
        js_function = "on_update_success" if success else "on_update_loss"
        log.note(f"BRIDGE -> JS: Enviando confirmación de {'ÉXITO' if success else 'FALLA'} para ID: {request_id}")
        self.view.page().runJavaScript(f"{js_function}('{json_response}');")