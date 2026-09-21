# nexi_app/view/main_window.py
from pathlib import Path

from PySide6.QtWidgets import QMainWindow, QApplication
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtCore import Qt, QUrl, QRect
from PySide6.QtGui import QRegion

from nexi_app.utils import log

import traceback
 
class MainWindow(QMainWindow):
    """
    La Vista (View) en el patrón MVC.
    Gestiona la ventana principal y todos los componentes de la UI.
    """
    def __init__(self, app: QApplication, config: dict):
        super().__init__()
        self.app = app
        self.setWindowTitle("Nexi Launcher")
        self._is_dragging = False
        self._last_mask = None

        # Configurar la ventana principal (sin bordes, siempre visible, etc.)
        self._apply_window_config(config)

        # Crear y configurar el QWebEngineView
        self.webview = QWebEngineView(self)

        # Configurar settings específicas
        settings = self.webview.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)

        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.AllowRunningInsecureContent, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard, True)

        self.setCentralWidget(self.webview)
        self._setup_webview_config(config)

        # Establecer una geometría y máscara inicial segura para evitar flashes
        self.setGeometry(QRect(0, 0, 1, 1))
        self.setMask(QRegion(0, 0, 1, 1, QRegion.Rectangle))

    def _apply_window_config(self, config: dict):
        """Aplica configuraciones de flags y atributos a la ventana."""
        flags = Qt.Window
        if config.get('flag_frameless'):
            flags |= Qt.FramelessWindowHint
        if config.get('flag_stay_on_top'):
            flags |= Qt.WindowStaysOnTopHint
        
        self.setWindowFlags(flags)
        
        if config.get('att_transparent_background'):
            self.setAttribute(Qt.WA_TranslucentBackground)
        log.info("Configuración de la ventana principal aplicada.")

    def _setup_webview_config(self, config: dict):
        """Aplica configuraciones al QWebEngineView."""
        if config.get('att_transparent_background'):
            self.page().setBackgroundColor(Qt.transparent)
        # =========================================================================
        # ✅ CORRECCIÓN: La llamada a .settings() se hace sobre self.webview
        # =========================================================================
        self.webview.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        log.info("Configuración del webview aplicada.")

    def page(self):
        """Acceso directo a la página del webview para el controlador."""
        return self.webview.page()

    def set_fullscreen(self, margin: int = 0):
         """Ajusta la ventana a pantalla completa con un margen opcional."""
 
         self.hide()
         screen_geometry = self.app.primaryScreen().availableGeometry()
         final_geometry = screen_geometry.adjusted(margin, margin, -margin, -margin)
         self.setGeometry(final_geometry)
    
         if margin > 0:  
          log.info(f"Geometría de ventana establecida con margen de seguridad {margin}px: {final_geometry.getRect()}")
 
         else:
             log.info(f"Geometría de ventana establecida a pantalla completa: {final_geometry.getRect()}")
 
         self.show()

    def set_dragging(self, dragging: bool):
        """
        Gestiona el modo de arrastre.
        - Al iniciar: limpia la máscara para permitir movimiento libre.
        - Al terminar: restaura la última máscara conocida.
        """
        if dragging and not self._is_dragging:
            self._is_dragging = True
            self.clearMask()
            log.note("MainWindow: Drag ON - máscara limpiada para movimiento libre.")
        elif not dragging and self._is_dragging:
            self._is_dragging = False
            if self._last_mask and not self._last_mask.isEmpty():
                self.setMask(self._last_mask)
                log.note("MainWindow: Drag OFF - máscara restaurada.")
            else:
                log.note("MainWindow: Drag OFF - sin máscara previa para restaurar.")

    def apply_mask(self, mask: QRegion):
        """Aplica una QRegion como máscara a la ventana."""
        self._last_mask = mask
        if not self._is_dragging:
            self.setMask(mask)

    def load_html(self, html_path: Path, js_paths: list[Path]):
        """Inyecta los scripts JS en el HTML y lo carga en el webview."""
        try:
            html_content = html_path.read_text(encoding='utf-8')
            all_js_content = "\n\n".join([js_path.read_text(encoding='utf-8') for js_path in js_paths])
            
            qwebchannel_script = '<script src="qrc:///qtwebchannel/qwebchannel.js"></script>'
            combined_scripts_tag = f'<script>{all_js_content}</script>'
            
            html_with_channel = html_content.replace('</head>', f'{qwebchannel_script}</head>', 1)
            parts = html_with_channel.rpartition('</body>')
            final_html = parts[0] + combined_scripts_tag + parts[1] + parts[2]
            
            self.webview.setHtml(final_html, baseUrl=QUrl.fromLocalFile(str(html_path.absolute())))
            js_names = [p.name for p in js_paths]
            log.info(f"HTML '{html_path.name}' cargado con JS {js_names} inyectado.")
        except FileNotFoundError as e:
            log.error(f"Archivo no encontrado durante la carga del HTML: {e}", exc_info=True)
            self.app.quit()