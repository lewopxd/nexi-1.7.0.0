# nexi_app/utils/hit_test_filter.py
import sys
import ctypes
from ctypes import wintypes
from PySide6.QtCore import QAbstractNativeEventFilter, QRect
from PySide6.QtWidgets import QWidget
from nexi_app.utils import log

WM_NCHITTEST = 0x0084
HTTRANSPARENT = -1
HTCLIENT = 1

class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", wintypes.POINT),
    ]

class HitTestFilter(QAbstractNativeEventFilter):
    """
    Filtro de eventos nativos de Windows (Win32) para gestionar el Hit-Testing
    en ventanas transparentes a pantalla completa.
    
    Intercepta WM_NCHITTEST y responde con:
      - HTTRANSPARENT (-1) si el cursor está en un área transparente (pasa el clic al escritorio/app inferior).
      - False (0) si el cursor está sobre un elemento activo (permite que Qt y Chromium procesen la interacción).
    """
    def __init__(self, window: QWidget):
        super().__init__()
        self.window = window
        self.active_hitboxes: list[dict] = []
        self.is_dragging: bool = False
        self.enabled: bool = True

    def set_hitboxes(self, hitboxes: list[dict]):
        """
        Actualiza las cajas de colisión activas.
        Cada hitbox debe ser un dict con:
          - 'rect': QRect
          - 'is_circle': bool (opcional)
        """
        self.active_hitboxes = hitboxes
        log.note(f"HitTestFilter: {len(hitboxes)} hitboxes actualizadas.")

    def set_dragging(self, dragging: bool):
        """Activa o desactiva el modo de arrastre continuo."""
        self.is_dragging = dragging
        log.note(f"HitTestFilter: Arrastre {'ACTIVADO' if dragging else 'DESACTIVADO'}.")

    def nativeEventFilter(self, eventType, message):
        if not self.enabled:
            return False, 0

        if eventType in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            msg = MSG.from_address(int(message))
            if msg.message == WM_NCHITTEST:
                # Si estamos arrastrando, permitimos que Nexi capture todos los eventos de mouse
                if self.is_dragging:
                    return False, 0

                # Coordenadas globales de pantalla (Win32 screen coords)
                x = ctypes.c_short(msg.lParam & 0xFFFF).value
                y = ctypes.c_short((msg.lParam >> 16) & 0xFFFF).value

                # Compensar geometría de la ventana y escalado DPI
                dpr = self.window.devicePixelRatio()
                win_geo = self.window.geometry()

                local_x = (x / dpr) - win_geo.x()
                local_y = (y / dpr) - win_geo.y()

                # Comprobar colisión contra cada hitbox activa
                for hb in self.active_hitboxes:
                    rect: QRect = hb.get('rect')
                    if rect is None:
                        continue

                    if hb.get('is_circle', False):
                        cx = rect.x() + rect.width() / 2.0
                        cy = rect.y() + rect.height() / 2.0
                        r = rect.width() / 2.0
                        if (local_x - cx) ** 2 + (local_y - cy) ** 2 <= r ** 2:
                            # Dentro de la silueta circular: dejar que Qt procese
                            return False, 0
                    else:
                        if rect.contains(int(local_x), int(local_y)):
                            # Dentro del rectángulo: dejar que Qt procese
                            return False, 0

                # Fuera de todos los elementos: transparente (pasa el clic al SO)
                return True, HTTRANSPARENT

        return False, 0
