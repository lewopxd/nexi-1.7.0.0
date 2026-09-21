# nexi_app/controller/main_controller.py
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QObject, Slot, QTimer, QRect
from PySide6.QtGui import QRegion

from nexi_app.view.main_window import MainWindow
from nexi_app.controller.bridge_controller import BridgeController # Importar el nuevo bridge
from nexi_app.utils import log

class MainController(QObject):
    """
    El Controlador (Controller) en el patrón MVC.
    Contiene la lógica de la aplicación, reaccionando a eventos
    comunicados por el BridgeController.
    """
    def __init__(self, view: MainWindow, app: QApplication, config: dict):
        super().__init__()
        self.view = view
        self.app = app
        self.bridge: BridgeController = None # Referencia al bridge se establecerá después
        self.security_margin = config.get('security_margin', 0)
        
        self.master_dictionary = {}
        self.final_masks = {}
        log.info("MainController: Diccionarios 'master_dictionary' y 'final_masks' inicializados.")

    def set_bridge(self, bridge: BridgeController):
        """Establece la referencia al bridge y conecta las señales a los slots."""
        self.bridge = bridge
        self.bridge.js_ready.connect(self.on_js_ready)
        self.bridge.update_received.connect(self.on_update_received)
        self.bridge.change_received.connect(self.on_change_received)
        log.info("MainController: Referencia al Bridge establecida y señales conectadas.")

    @Slot(bool, str)
    def on_js_ready(self, success: bool, message: str):
        """Maneja la señal de que JS está listo."""
        if hasattr(self, '_js_ready_executed') and self._js_ready_executed:
            log.alert(f"on_js_ready YA EJECUTADO - Ignorando señal duplicada: {message}")
            return
        
        self._js_ready_executed = True
        log.note(f"CONTROLLER: Lógica de 'on_js_ready' ejecutada.")
        
        self.view.set_fullscreen(margin=self.security_margin)
        log.info("CONTROLLER: Esperando 100ms para estabilización del renderizado...")
        QTimer.singleShot(100, self.bridge.send_python_ready_confirmation)

    @Slot(dict)
    def on_update_received(self, data: dict):
        """Maneja los mensajes de tipo 'update' para actualizar el diccionario maestro."""
        request_id = data.get("id")
        log.note(f"CONTROLLER: Procesando 'update' con ID: {request_id}")
        self.master_dictionary = data.get("msg", {})
        self._precalculate_all_masks()
        self.bridge.send_confirmation(request_id, success=True)

    @Slot(dict)
    def on_change_received(self, data: dict):
        """Maneja los mensajes de tipo 'change' para cambiar la escena visible."""
        request_id = data.get("id")
        scene_to_change = str(data.get("sc"))
        log.note(f"CONTROLLER: Procesando 'change' para escena '{scene_to_change}' (ID: {request_id})")
        
        mask = self.final_masks.get(scene_to_change)
        if mask is not None:
            log.note(f"Aplicando máscara para escena '{scene_to_change}'.")
            self.view.apply_mask(mask)
            self.bridge.send_confirmation(request_id, success=True)
        else:
            log.error(f"No se encontró máscara para la escena '{scene_to_change}'.")
            self.bridge.send_confirmation(request_id, success=False)
    
    def _precalculate_all_masks(self):
        """Pre-calcula y cachea todas las máscaras de colisión para un rendimiento óptimo."""
        log.note("--- Iniciando pre-cálculo y cacheo de máscaras ---")
        self.final_masks.clear()
        if not self.master_dictionary:
            log.alert("El diccionario maestro está vacío; no se pueden calcular máscaras.")
            return

        window_offset = self.view.geometry().topLeft()

        character_masks_normalized = {}
        characters = self.master_dictionary.get('characters', {})
        for char_name, char_data in characters.items():
            ch_index = char_data.get('ch')
            geo = char_data.get('geometry', {})
            shape = char_data.get('shape', {})
            
            rect = QRect(
                round(geo.get('x', 0)), round(geo.get('y', 0)),
                round(geo.get('width', 0)), round(geo.get('height', 0))
            )
            
            if shape.get('borderRadius') == '50%':
                character_masks_normalized[ch_index] = QRegion(rect, QRegion.Ellipse)
            else:
                character_masks_normalized[ch_index] = QRegion(rect, QRegion.Rectangle)

        scenes = self.master_dictionary.get('scenes', {})
        for scene_id, scene_data in scenes.items():
            normalized_scene_mask = QRegion()
            orchestration = scene_data.get('orchest', [])
            for ch_index in orchestration:
                if ch_index in character_masks_normalized:
                    normalized_scene_mask = normalized_scene_mask.united(character_masks_normalized[ch_index])
            str_scene_id = str(scene_id)
            self.final_masks[str_scene_id] = normalized_scene_mask.translated(window_offset)

        screen_geometry = self.app.primaryScreen().availableGeometry()
        fullscreen_rect = screen_geometry.adjusted(self.security_margin, self.security_margin, -self.security_margin, -self.security_margin)
        self.final_masks['0'] = QRegion(fullscreen_rect)
        
        log.note(f"--- Proceso completado. {len(self.final_masks)} máscaras de escena cacheadas. ---")