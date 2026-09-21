import sys
import os
from PySide6.QtCore import QSharedMemory
from pathlib import Path

def resource_path(relative_path):
    """ Obtiene la ruta absoluta al recurso, funciona para desarrollo y para PyInstaller. """
    try:
        # PyInstaller crea una carpeta temporal y guarda la ruta en _MEIPASS
        base_path = Path(sys._MEIPASS)
    except Exception:
        # Si no está empaquetado, la base es el directorio del script principal
        base_path = Path(__file__).resolve().parent.parent.parent # Sube tres niveles (de utils a nexi_app y de ahí a la raíz)

    return base_path / relative_path

def is_first_instance(lock_key):
    """
    Comprueba si ya existe una instancia de la aplicación.
    
    Returns:
        tuple[bool, QSharedMemory]: (True, memory_object) si es la primera instancia,
                                     (False, None) si ya existe otra.
    """
    shared_memory = QSharedMemory(lock_key)
    
    if shared_memory.attach():
        return (False, None)
        
    if not shared_memory.create(1):
        return (False, None)
        
    return (True, shared_memory)