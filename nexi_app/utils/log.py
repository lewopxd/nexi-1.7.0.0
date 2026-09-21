# nexi_app/utils/log.py
import os
import sys
import inspect
import json
import socket
from datetime import datetime
from pathlib import Path

from nexi_app.utils.helpers import resource_path
  


# ================== 🔧 CONFIGURACIÓN GLOBAL ==================
VERSION = "1.6.0"

# --- Niveles de Log ---
ALL_ENABLED = True
INFO_ENABLED = True
ERROR_ENABLED = True
ALERT_ENABLED = True
NOTE_ENABLED = True

# --- Rutas de Archivos (relativas a la raíz del proyecto) ---
LOG_DIR = ".logs"
LOG_FILE = os.path.join(LOG_DIR, ".logs")
CONF_FILE = os.path.join(LOG_DIR, ".info")
VIEWER_FILE = os.path.join(LOG_DIR, "viewer.html")
TEMPLATE_DIR = resource_path(os.path.join("resources", "templates", "log_viewer_template"))

# --- Formato y Ancho ---
MAX_TYPE_LENGTH = 7  # [ERROR] es el más largo
EXTRA_SPACES_AFTER = 2
TOTAL_PREFIX_WIDTH = MAX_TYPE_LENGTH + EXTRA_SPACES_AFTER
SHORT_FIELD_WIDTH = 15 # Ancho fijo para el campo de archivo en modo 'short'

# ================== 🎨 COLORES ANSI (para la consola) ==================
RESET = "\u001B[0m"
INFO_COLOR = "\u001B[36m"   # Cyan
ERROR_COLOR = "\u001B[31m"  # Rojo
ALERT_COLOR = "\u001B[33m"  # Amarillo
NOTE_COLOR = "\u001B[32m"   # Verde

COLORS = {
    "INFO": INFO_COLOR,
    "ERROR": ERROR_COLOR,
    "ALERT": ALERT_COLOR,
    "NOTE": NOTE_COLOR,
}

# ================== 🕰️ FORMATO DE TIEMPO ==================
FORMATTER = "%Y%m%d_%H:%M:%S.%f"

# ================== 👤 ESTADO GLOBAL (privado para el módulo) ==================
_user_name = None
_initialized = False
_session_id = None
_log_mode = "normal"  # 'normal' o 'short'


# ================== 🛠️ GESTIÓN DE SESIONES ==================
def _generate_session_id():
    """Genera un ID de sesión único basado en el tiempo."""
    return f"sid_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"


def _update_info_json(version):
    """
    Crea o actualiza el archivo nexi.version con la versión actual de Nexi.
    Este archivo centraliza la versión del proyecto para ser consultada por otros módulos.
    """
    # Navega tres niveles hacia arriba desde el archivo actual (log.py -> utils -> nexi_app -> raíz)
    project_root = Path(__file__).resolve().parent.parent.parent
    version_file_path = project_root / "nexi.version"

    # Prepara el contenido del archivo JSON
    data = {
        "nexi_version": version
    }

    # Escribe o sobreescribe el archivo con la nueva versión
    try:
        with open(version_file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except IOError as e:
        # Usar el propio sistema de log para reportar el fallo es una mala práctica
        # ya que puede causar un bucle infinito si el log aún no está inicializado.
        # Imprimir directamente al error estándar es más seguro en este contexto.
        print(f"❌ Error al escribir en '{version_file_path}': {e}", file=sys.stderr)
    """
    Crea o actualiza el archivo info.json con la versión de Nexi y el main path del proyecto.
    Si el archivo no existe, lo crea. Si existe, solo actualiza la versión.
    """
    project_root = Path(__file__).resolve().parent.parent.parent  # Ajusta según tu estructura
    info_json_path = project_root / "info.json"

    if not info_json_path.exists():
        # Crear archivo info.json con la versión y el main path
        data = {
            "nexi_version": version,
            "main_path": str(project_root)
        }
        with open(info_json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    else:
        # Actualizar solo la versión
        try:
            with open(info_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
        data["nexi_version"] = version
        with open(info_json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)


def start_session(name="null:null", version=None, mode="normal"):
    """
    Inicia una nueva sesión de logs. Si el sistema no está inicializado,
    lo prepara creando los archivos y directorios necesarios.
    Permite opcionalmente establecer la versión de la app y el modo de consola.
    """
    global _initialized, _session_id, VERSION, _log_mode
    _log_mode = mode
    if name != "null:null":
        set_name(name)
    if version is not None:
        VERSION = version
        _update_info_json(version)
    if not _initialized:
        init()
    _session_id = _generate_session_id()
    info(f"New Session started: {_session_id} (version={VERSION}, mode={_log_mode})")


# ================== 🔍 FUNCIÓN DE LOGGING CENTRAL ==================
def _log(log_type, message):
    """
    Función interna que maneja toda la lógica de registro:
    formateo, obtención de datos del llamador y escritura en consola y archivo.
    """
    if not _initialized:
        init()

    if _session_id is None:
        start_session()

    # --- Obtener información del llamador usando el módulo inspect ---
    try:
        # Buscamos en el stack hasta encontrar un frame fuera de este módulo.
        caller_frame = inspect.currentframe()
        while caller_frame and caller_frame.f_globals['__name__'] == __name__:
            caller_frame = caller_frame.f_back

        if caller_frame:
            caller_info = inspect.getframeinfo(caller_frame)
            filename = os.path.basename(caller_info.filename)
            lineno = caller_info.lineno
        else:
            raise ValueError("No se pudo encontrar el frame del llamador.")

    except Exception:
        filename = "Unknown.py"
        lineno = -1

    # --- Formatear mensaje ---
    bracketed = f"[{log_type}]"
    timestamp = datetime.now().strftime(FORMATTER)[:-3]  # Truncar a milisegundos
    name_part = f"by@{_user_name}" if _user_name else ""

    # Formato para archivo (siempre es completo)
    file_prefix = f"{bracketed:<{TOTAL_PREFIX_WIDTH}}"
    file_formatted = f"{_session_id}, {file_prefix}, {timestamp}, {name_part}, in {filename}({lineno}), > {message}\n"

    # Formato para consola (depende del modo)
    if _log_mode == "short":
        file_info = f"{filename}({lineno})"
        
        # Lógica para ajustar el campo a 15 caracteres
        if len(file_info) <= SHORT_FIELD_WIDTH:
            # Si es menor o igual, rellenar con espacios
            formatted_file_info = f"{file_info:<{SHORT_FIELD_WIDTH}}"
        else:
            # Si es mayor, truncar el nombre del archivo en el medio
            chars_to_keep = SHORT_FIELD_WIDTH - 3 # Dejar espacio para "..."
            line_part = f"({lineno})"
            filename_part_len = chars_to_keep - len(line_part)
            
            if filename_part_len > 0:
                # Trunca el filename, no la info completa
                truncated_filename = f"{filename[:filename_part_len - 2]}...{filename[-2:]}"
                formatted_file_info = f"{truncated_filename}{line_part}"
                # Re-ajuste final por si acaso
                formatted_file_info = f"{formatted_file_info:<{SHORT_FIELD_WIDTH}}"
            else:
                # Si ni siquiera cabe el nombre truncado, truncar la cadena completa
                keep_start = (SHORT_FIELD_WIDTH - 3) // 2
                keep_end = SHORT_FIELD_WIDTH - 3 - keep_start
                formatted_file_info = f"{file_info[:keep_start]}...{file_info[-keep_end:]}"

        console_formatted = f"[{log_type.lower()}] > {formatted_file_info} > {message}"
    else: # Modo "normal"
        prefix = f"{bracketed:<{TOTAL_PREFIX_WIDTH}}"
        console_formatted = f"{prefix}{timestamp} {name_part} in {filename}({lineno}) > {message}"

    # --- Escribir en archivo ---
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(file_formatted)
    except IOError as e:
        print(f"❌ No se pudo escribir en {LOG_FILE}: {e}", file=sys.stderr)

    # --- Mostrar en consola si está habilitado ---
    if ALL_ENABLED and _is_enabled(log_type):
        color = COLORS.get(log_type, RESET)
        print(color + console_formatted + RESET)


# ================== 🔌 CONTROL DE NIVELES DE LOG ==================
def _is_enabled(log_type):
    """Verifica si un nivel de log específico está habilitado."""
    return {
        "INFO": INFO_ENABLED,
        "ERROR": ERROR_ENABLED,
        "ALERT": ALERT_ENABLED,
        "NOTE": NOTE_ENABLED,
    }.get(log_type, True)


# ================== 🛠️ INICIALIZACIÓN DEL SISTEMA DE LOGS ==================
def init():
    """
    Prepara el entorno de logging. Se ejecuta una sola vez.
    Crea el directorio .logs y los archivos de configuración y log.
    """
    global _initialized
    if _initialized:
        return

    try:
        # 1. Crear carpeta .logs si no existe
        if not os.path.exists(LOG_DIR):
            os.makedirs(LOG_DIR)
            print("📁 Carpeta .logs creada")

        # 2. Crear archivo de log si no existe y escribir metadatos
        if not os.path.exists(LOG_FILE):
            with open(LOG_FILE, "w", encoding="utf-8") as f:
                meta = {
                    "created": datetime.now().isoformat(),
                    "python": sys.version.split()[0],
                    "os": f"{sys.platform}",
                    "user": os.getlogin(),
                    "host": socket.gethostname()
                }
                f.write(f"##META: {json.dumps(meta)}\n")
            print("📄 Archivo log creado")

        # 3. Crear archivo de configuración .info
        if not os.path.exists(CONF_FILE):
            _create_config_file()

        # 4. Crear viewer.html desde la plantilla
        if not os.path.exists(VIEWER_FILE):
            _create_viewer_file()

        _initialized = True

    except Exception as e:
        print(f"❌ Error al inicializar logs: {e}", file=sys.stderr)


# ================== 🛠️ CREACIÓN DE ARCHIVOS AUXILIARES ==================
def _read_resource(file_path):
    """Lee un archivo de recurso y devuelve su contenido."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"❌ No se encontró el recurso: {file_path}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"❌ Error al leer el recurso {file_path}: {e}", file=sys.stderr)
        return None


def _create_viewer_file():
    """Crea el viewer.html ensamblando los archivos de la plantilla."""
    html_path = os.path.join(TEMPLATE_DIR, "index.html")
    css_path = os.path.join(TEMPLATE_DIR, "style.css")
    js_path = os.path.join(TEMPLATE_DIR, "script.js")

    html_content = _read_resource(html_path)
    css_content = _read_resource(css_path)
    js_content = _read_resource(js_path)

    if not all([html_content, css_content, js_content]):
        print("⚠️ Faltan archivos de plantilla. Creando visor de respaldo.", file=sys.stderr)
        _create_fallback_viewer()
        return

    # Ensamblar el HTML final inyectando CSS y JS
    final_html = html_content
    final_html = final_html.replace('<link rel="stylesheet" href="style.css">', f"<style>{css_content}</style>")
    final_html = final_html.replace('<script src="script.js" defer></script>', f"<script>{js_content}</script>")
    final_html = final_html.replace('<script src="script.js"></script>', f"<script>{js_content}</script>")

    try:
        with open(VIEWER_FILE, "w", encoding="utf-8") as f:
            f.write(final_html)
        print(f"✅ viewer.html creado exitosamente desde la plantilla: {os.path.abspath(VIEWER_FILE)}")
    except IOError as e:
        print(f"❌ No se pudo escribir viewer.html: {e}", file=sys.stderr)
        _create_fallback_viewer()


def _create_fallback_viewer():
    """Crea un visor HTML básico de respaldo si la plantilla falla."""
    fallback_html = """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Nexi Log Viewer (Fallback)</title>
        <style>body { font-family: monospace; background-color: #1e1e1e; color: #d4d4d4; }</style>
    </head>
    <body>
        <h1>⚠️ Viewer no disponible</h1>
        <p>No se pudo cargar la plantilla. Asegúrate de que la carpeta <code>resources/template/log_viewer_template/</code> exista y contenga <code>index.html</code>, <code>style.css</code>, y <code>script.js</code>.</p>
    </body>
    </html>
    """
    try:
        with open(VIEWER_FILE, "w", encoding="utf-8") as f:
            f.write(fallback_html)
    except IOError as e:
        print(f"❌ No se pudo escribir ni el visor de respaldo: {e}", file=sys.stderr)


def _create_config_file():
    """Crea el archivo de configuración .info con detalles del entorno."""
    content = [
        "## Log Configuration",
        f"created={datetime.now().isoformat()}",
        f"version={VERSION}",
        f"python.version={sys.version.split()[0]}",
        f"os.name={sys.platform}",
        f"user={os.getlogin()}",
        f"host={socket.gethostname()}",
        "log.level=INFO,ERROR,ALERT,NOTE"
    ]
    with open(CONF_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(content))


# ================== 🛠️ MÉTODOS PÚBLICOS DE LOGGING ==================
def set_name(logger_name):
    """Establece el nombre de usuario para los logs."""
    global _user_name
    _user_name = logger_name


def clear_name():
    """Limpia el nombre de usuario de los logs."""
    global _user_name
    _user_name = None


def get_session_id():
    """Devuelve el ID de la sesión actual, iniciando una si no existe."""
    if _session_id is None:
        start_session()
    return _session_id


def info(message, exc_info=False):
    """Registra un mensaje de tipo INFO."""
    if ALL_ENABLED and INFO_ENABLED:
        _log("INFO", message)
        if exc_info: _log_exception()


def error(message, exc_info=False):
    """Registra un mensaje de tipo ERROR."""
    if ALL_ENABLED and ERROR_ENABLED:
        _log("ERROR", message)
        if exc_info: _log_exception()


def alert(message, exc_info=False):
    """Registra un mensaje de tipo ALERT."""
    if ALL_ENABLED and ALERT_ENABLED:
        _log("ALERT", message)
        if exc_info: _log_exception()


def note(message, exc_info=False):
    """Registra un mensaje de tipo NOTE."""
    if ALL_ENABLED and NOTE_ENABLED:
        _log("NOTE", message)
        if exc_info: _log_exception()


# ================== 🧩 REGISTRO DE EXCEPCIONES COMPLETAS ==================
def _log_exception():
    """Registra la traza completa de una excepción en el log."""
    import traceback
    exc_type, exc_value, exc_tb = sys.exc_info()
    tb_lines = traceback.format_exception(exc_type, exc_value, exc_tb)
    for line in "".join(tb_lines).splitlines():
        _log("ERROR", f"  {line.strip()}")


# ================== 🧪 EJEMPLO DE USO (si se ejecuta el archivo directamente) ==================
if __name__ == "__main__":
    print("Ejecutando demo del módulo de logging...")

    # Para que la demo funcione, crea una estructura de carpetas de ejemplo:
    if not os.path.exists(TEMPLATE_DIR):
        os.makedirs(os.path.join(TEMPLATE_DIR, "css"))
        os.makedirs(os.path.join(TEMPLATE_DIR, "js"))
        with open(os.path.join(TEMPLATE_DIR, "index.html"), "w") as f:
            f.write(
                '<!DOCTYPE html><html><head><link rel="stylesheet" href="style.css"></head><body><h1>Test Viewer</h1><script src="script.js"></script></body></html>')
        with open(os.path.join(TEMPLATE_DIR, "style.css"), "w") as f:
            f.write('body { color: blue; }')
        with open(os.path.join(TEMPLATE_DIR, "script.js"), "w") as f:
            f.write("console.log('Hello from template');")
        print("📁 Plantilla de demo creada.")

    print("\n--- DEMO MODO SHORT ---")
    start_session("nexi-app", "1.6.0", "short")
    note("Mensaje de prueba.")
    
    # Simular una llamada desde un archivo con nombre largo
    _log("NOTE", "Mensaje desde un archivo con nombre muy largo para demostración.")

    print("\n--- DEMO MODO NORMAL ---")
    start_session("lynda-dev", "1.6.0", "normal")
    info("Este es un mensaje informativo.")
    
    try:
        result = 1 / 0
    except ZeroDivisionError:
        error("No se puede dividir por cero.", exc_info=True)

    print(f"\nDemo finalizada. Revisa la carpeta '{LOG_DIR}' para ver los resultados.")