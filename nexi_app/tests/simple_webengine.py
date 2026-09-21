import sys
import os
import logging
from pathlib import Path

# --- Importaciones de PySide6 ---
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtCore import Qt, QUrl, QSize

# ===================================================================
# 🔹 1. CONFIGURACIÓN
# ===================================================================
# Archivo HTML que se cargará en la ventana.
TARGET_FILE_PATH = "resources/web_designs/sphere/sphere-5.76.html"

# Diccionario para configurar el comportamiento y la apariencia de la ventana.
WINDOW_CONFIG = {
    # --- Apariencia ---
    'flag_frameless': True,  # True: sin bordes ni barra de título.
    'flag_stay_on_top': False,  # True: la ventana siempre estará por encima de otras.
    'att_transparent_background': True,  # True: fondo de la ventana transparente (requiere HTML/CSS adecuado).

    # --- Comportamiento ---
    'feature_resizable': True,  # True: permite cambiar el tamaño de la ventana.
    'feature_dev_tools': True,  # True: habilita las herramientas de desarrollador web en el puerto 9222.
}

# Tamaño inicial con el que se creará la ventana.
INITIAL_WINDOW_SIZE = QSize(1280, 720)

# ===================================================================
# 🔹 2. LOGGER
# ===================================================================
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
log = logging.getLogger(__name__)


# ===================================================================
# 🔹 3. CLASE PRINCIPAL DE LA VENTANA
# ===================================================================
class WebViewerWindow(QMainWindow):
    """
    Ventana principal que aloja un QWebEngineView para renderizar contenido web local.
    La configuración se aplica dinámicamente desde un diccionario.
    """

    def __init__(self, file_path: str, config: dict):
        super().__init__()
        self.file_path = file_path
        self.config = config

        self.setWindowTitle(f"Nexi Web Viewer - {self.file_path}")
        self._apply_config()
        self._setup_ui()

    def _apply_config(self):
        """Aplica la configuración del diccionario a la ventana."""
        log.info("Aplicando configuración de la ventana...")
        final_flags = Qt.Window

        if self.config.get('flag_frameless'):
            final_flags |= Qt.FramelessWindowHint
        if self.config.get('flag_stay_on_top'):
            final_flags |= Qt.WindowStaysOnTopHint

        self.setWindowFlags(final_flags)

        if self.config.get('att_transparent_background'):
            self.setAttribute(Qt.WA_TranslucentBackground)


        self.resize(INITIAL_WINDOW_SIZE)

        if not self.config.get('feature_resizable', True):
            self.setFixedSize(INITIAL_WINDOW_SIZE)

    def _setup_ui(self):
        """Configura e inicializa el widget de la vista web."""
        log.info("Configurando la vista web...")
        self.webview = QWebEngineView(self)

        self.webview.page().setBackgroundColor(Qt.transparent)
        self.setCentralWidget(self.webview)

        # Conectar señales para logging del proceso de carga.
        self.webview.loadStarted.connect(lambda: log.info(f"Iniciando carga de: {self.file_path}"))
        self.webview.loadProgress.connect(lambda p: log.info(f"Progreso de carga: {p}%"))
        self.webview.loadFinished.connect(self._on_load_finished)

        # Configurar settings específicas
        settings = self.webview.settings()
       # settings.setAttribute(QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled, True)
       # settings.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)

        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.AllowRunningInsecureContent, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard, True)
        

        # Cargar el archivo HTML local.
        local_url = QUrl.fromLocalFile(str(Path(self.file_path).resolve()))
        self.webview.load(local_url)

    def _on_load_finished(self, success: bool):
        """Se ejecuta cuando la página ha terminado de cargar."""
        if success:
            log.info(f"Página '{self.webview.title()}' cargada con éxito.")
        else:
            log.error(f"Fallo al cargar el archivo: {self.file_path}")


# ===================================================================
# 🔹 4. PUNTO DE ENTRADA Y CONFIGURACIÓN DEL ENTORNO
# ===================================================================
def setup_environment(config: dict):
    """Configura variables de entorno antes de inicializar la app."""
    if config.get('feature_dev_tools'):
        os.environ['QTWEBENGINE_REMOTE_DEBUGGING'] = "9222"
        log.info("DevTools habilitado. Accede desde un navegador en http://localhost:9222")


def main():
    """Función principal que lanza la aplicación."""
    log.info("========================================")
    log.info("||     INICIANDO NEXI WEB VIEWER      ||")
    log.info("========================================")

    setup_environment(WINDOW_CONFIG)

    app = QApplication(sys.argv)

    target_path = Path(TARGET_FILE_PATH)
    if not target_path.exists():
        log.error(f"Error: El archivo de destino '{TARGET_FILE_PATH}' no fue encontrado.")
        sys.exit(1)

    viewer_window = WebViewerWindow(file_path=str(target_path), config=WINDOW_CONFIG)
    viewer_window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()