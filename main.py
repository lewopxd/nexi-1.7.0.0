# main.py
import sys
import os
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox
from nexi_app.utils.system_info import SystemInfo
from nexi_app.view.main_window import MainWindow
from nexi_app.controller.main_controller import MainController
from nexi_app.controller.bridge_controller import BridgeController
from nexi_app.utils import log

# =========================================================================
# ✅ CAMBIO: Importar las nuevas funciones de ayuda
# =========================================================================
from nexi_app.utils.helpers import resource_path, is_first_instance

# --- 🔹 CONFIGURACIÓN GLOBAL DE LA VENTANA ---
WINDOW_CONFIG = {
    'flag_frameless': True,
    'flag_stay_on_top': True,
    'att_transparent_background': True,
    'feature_dev_tools': False,
    'security_margin': 1
}

def setup_environment(config: dict):
    """Configura variables de entorno, como el puerto de depuración."""
    if config.get('feature_dev_tools'):
        port = "9222"
        os.environ['QTWEBENGINE_REMOTE_DEBUGGING'] = port
        log.info(f"DevTools habilitadas. Accede en: http://localhost:{port}")

def main():
    log.start_session("nexi-app", "1.6.0", "short")
    log.info("================ INICIANDO NEXI MVC ================")

    # =========================================================================
    # ✅ CAMBIO: Mover la creación de QApplication al inicio y añadir el lock
    # =========================================================================
    app = QApplication(sys.argv)
    
    APP_LOCK_KEY = "nexi-app-unique-lock-key-a1b2c3d4"
    is_first, memory_lock = is_first_instance(APP_LOCK_KEY)
    
    if not is_first:
        log.warn("Se intentó abrir una segunda instancia. Cerrando.")
        QMessageBox.warning(None, "Nexi App", "La aplicación ya se está ejecutando.")
        sys.exit(0)
    
    # Aseguramos que el lock se libere al cerrar la aplicación
    app.aboutToQuit.connect(memory_lock.detach)
    # =========================================================================

    # --- 🔹 RUTAS A ARCHIVOS (usando la nueva función para compatibilidad con PyInstaller) ---
    html_file_path = resource_path(Path("resources")  / "web_designs" / "nexi-orchester" / "nexi-orchester.html")
    scripts_to_inject = [
        resource_path(Path("resources") /  "web_designs" / "nexi-orchester" / "js" / "nexi_bus.js"),
        resource_path(Path("resources") /  "web_designs" / "nexi-orchester" / "js" / "mask_engine.js"),
        resource_path(Path("resources") /  "web_designs" / "nexi-orchester" / "js" / "bridge_engine.js")
    ]
    
    log.info("Generando informe del sistema...")
    # ✅ CAMBIO: La raíz del proyecto ahora se obtiene desde la función de ayuda
    project_root = resource_path(Path("."))
    info_updater = SystemInfo(project_root=project_root)
    system_report = info_updater.get_info()
    log.info(system_report)

    if not html_file_path.exists():
        log.error(f"CRÍTICO: No se encuentra el orquestador en: {html_file_path}")
        sys.exit(-1)

    setup_environment(WINDOW_CONFIG)
    
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--ignore-gpu-blocklist --enable-gpu-rasterization"
    
    # --- 🔹 INICIALIZACIÓN MVC (el resto del código no cambia) ---
    view = MainWindow(app, WINDOW_CONFIG)
    main_controller = MainController(view, app, WINDOW_CONFIG)
    bridge_controller = BridgeController(view)
    main_controller.set_bridge(bridge_controller)
    
    view.show()
    view.load_html(html_file_path, scripts_to_inject)
    
    log.info("Aplicación iniciada. Esperando handshake de JavaScript...")
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()