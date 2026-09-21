# nexi_app/utils/system_info.py

import json
import platform
import subprocess
import sys
from pathlib import Path

# Dependencias de terceros: pip install psutil WMI
try:
    import psutil
    import wmi
except ImportError:
    print("Error: Las librerías 'psutil' y 'WMI' son necesarias. Instálalas con 'pip install psutil WMI'")
    sys.exit(1)

from nexi_app.utils import log


class SystemInfo:
    """
    Clase para leer, actualizar con información del sistema en tiempo real
    y guardar el archivo de configuración info.json.
    """

    def __init__(self, project_root: Path):
        """
        Inicializa la clase con la ruta raíz del proyecto.

        Args:
            project_root (Path): El objeto Path a la carpeta raíz del proyecto.
        """
        self.project_root = project_root
        self.info_json_path = self.project_root / "info.json"
        self.requirements_path = self.project_root / "requirements.txt"
        self.wmi_con = wmi.WMI()

    def _robust_file_read(self, file_path: Path) -> str | None:
        """
        Lee un archivo de texto de forma robusta, probando varias codificaciones comunes.
        """
        try:
            with open(file_path, 'rb') as f:
                content_bytes = f.read()

            for encoding in ['utf-8-sig', 'utf-16', 'utf-8', 'latin-1']:
                try:
                    return content_bytes.decode(encoding)
                except UnicodeDecodeError:
                    continue

            log.error(f"No se pudo decodificar el archivo '{file_path}' con las codificaciones probadas.")
            return None
        except IOError as e:
            log.error(f"No se pudo leer el archivo '{file_path}': {e}", exc_info=True)
            return None

    def _read_existing_info(self) -> dict:
        """Lee el archivo info.json existente y lo devuelve como un diccionario."""
        if not self.info_json_path.exists():
            return {}

        content = self._robust_file_read(self.info_json_path)
        if content is None:
            return {}

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            log.error(f"No se pudo parsear el JSON de '{self.info_json_path}': {e}", exc_info=True)
            return {}

    def _get_dev_versions(self) -> dict:
        """Obtiene las versiones de las herramientas de desarrollo."""
        try:
            pip_version = subprocess.check_output([sys.executable, '-m', 'pip', '--version']).decode('utf-8').split()[1]
        except Exception:
            pip_version = "No encontrado"

        return {
            "python": platform.python_version(),
            "pip": pip_version
        }

    def _get_system_environment(self) -> dict:
        """Obtiene la información completa del hardware y SO."""
        try:
            os_info = self.wmi_con.Win32_OperatingSystem()[0]
        except Exception:
            os_info = None

        try:
            cs_info = self.wmi_con.Win32_ComputerSystem()[0]
        except Exception:
            cs_info = None

        try:
            processor_info = self.wmi_con.Win32_Processor()[0]
        except Exception:
            processor_info = None

        try:
            gpu_info = self.wmi_con.Win32_VideoController()[0]
        except Exception:
            gpu_info = None

        try:
            storage_devices = [
                {"model": disk.Model, "size_gb": round(int(disk.Size) / (1024 ** 3), 2)}
                for disk in self.wmi_con.Win32_DiskDrive()
            ]
        except Exception:
            storage_devices = []

        bytes_to_gb = lambda b: round(b / (1024 ** 3), 2) if b else None

        return {
            "os": {
                "nombre": getattr(os_info, "Caption", "N/A") if os_info else "N/A",
                "version": getattr(os_info, "Version", "N/A") if os_info else "N/A",
                "arquitectura": getattr(cs_info, "SystemType", "N/A") if cs_info else "N/A"
            },
            "hardware": {
                "fabricante": getattr(cs_info, "Manufacturer", "N/A") if cs_info else "N/A",
                "modelo": getattr(cs_info, "Model", "N/A") if cs_info else "N/A",
                "procesador": getattr(processor_info, "Name", "N/A").strip() if processor_info else "N/A",
                "ram": {"size_gb": bytes_to_gb(int(getattr(cs_info, "TotalPhysicalMemory", 0))) if cs_info else "N/A"},
                "gpu": {
                    "name": getattr(gpu_info, "Name", "N/A") if gpu_info else "N/A",
                    "vram_gb": bytes_to_gb(getattr(gpu_info, "AdapterRAM", 0)) if gpu_info else "N/A"
                },
                "storage": storage_devices
            },
            "configuracion": {
                "region": getattr(os_info, "CountryCode", "N/A") if os_info else "N/A"
            }
        }

    def _get_requirements(self) -> dict:
        """Lee el archivo requirements.txt y lo convierte en un diccionario."""
        if not self.requirements_path.exists():
            log.alert(f"El archivo '{self.requirements_path}' no fue encontrado.")
            return {}

        content = self._robust_file_read(self.requirements_path)
        if content is None:
            return {}

        reqs = {}
        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith('#'):
                if '==' in line:
                    name, version = line.split('==', 1)
                    reqs[name] = version
                else:
                    reqs[line] = "latest"
        return reqs

    def _write_info_file(self, data: dict):
        """Escribe el diccionario actualizado de vuelta a info.json."""
        try:
            with open(self.info_json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            log.info(f"El archivo info.json ha sido actualizado exitosamente. > '{self.info_json_path}'")
        except IOError as e:
            log.error(f"No se pudo escribir en '{self.info_json_path}': {e}", exc_info=True)

    def _get_nexi_version(self) -> str:
        """Lee la versión de Nexi desde un archivo de versión dedicado."""
        version_file = self.project_root / "nexi.version"
        if not version_file.exists():
            log.error(f"El archivo de versión '{version_file}' no existe.")
            return "N/A"
        
        try:
            with open(version_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("nexi_version", "N/A")
        except Exception as e:
            log.error(f"No se pudo leer la versión de Nexi desde '{version_file}': {e}", exc_info=True)
            return "N/A"

    def update_info_file(self) -> dict:
        """
        Orquesta el proceso de forma robusta: lee o crea la estructura base,
        obtiene datos, actualiza y guarda. Devuelve el diccionario actualizado.
        """
        log.info("Iniciando actualización del archivo info.json...")

        info_data = self._read_existing_info()
        if not info_data:
            log.alert(f"'{self.info_json_path}' no encontrado o corrupto. Creando estructura base.")
            info_data = {
                "nexi_version": self._get_nexi_version(),
                # ==================================================================
                # CORRECCIÓN 1: Escribir la clave "main_path" para consistencia.
                # ==================================================================
                "main_path": str(self.project_root),
                "requirements": {},
                "dev_environment": {
                    "development_versions": {},
                    "system_environment": {}
                }
            }

        info_data['requirements'] = self._get_requirements()
        dev_env = info_data.setdefault('dev_environment', {})
        dev_env['development_versions'] = self._get_dev_versions()
        dev_env['system_environment'] = self._get_system_environment()
        
        self._write_info_file(info_data)
        
        return info_data


    def get_info(self) -> str:
        """Actualiza el archivo info.json y devuelve una cadena formateada."""
        data = self.update_info_file()
        
        if not data:
            return "No se pudo obtener la información del sistema."

        lines = ["\n--- System Information ---"]
        lines.append(f"  Nexi Version: {data.get('nexi_version', 'N/A')}")
        # ==================================================================
        # CORRECCIÓN 2: Leer la clave "main_path" que sabemos que existe.
        # ==================================================================
        lines.append(f"  Project Path: {data.get('main_path', 'N/A')}")
        lines.append("-" * 20)

        dev_env = data.get('dev_environment', {})
        dev_versions = dev_env.get('development_versions', {})
        lines.append("  Development Environment:")
        for key, value in dev_versions.items():
            lines.append(f"    - {key.capitalize()}: {value}")
        lines.append("-" * 20)

        sys_env = dev_env.get('system_environment', {})
        lines.append("  System Environment:")
        lines.append(
            f"    OS: {sys_env.get('os', {}).get('nombre', 'N/A')} ({sys_env.get('os', {}).get('arquitectura', 'N/A')})")
        hardware = sys_env.get('hardware', {})
        lines.append(f"    Hardware: {hardware.get('fabricante', '')} {hardware.get('modelo', '')}")
        lines.append(f"    CPU: {hardware.get('procesador', 'N/A')}")
        lines.append(f"    RAM: {hardware.get('ram', {}).get('size_gb', 'N/A')} GB")
        lines.append(
            f"    GPU: {hardware.get('gpu', {}).get('name', 'N/A')} ({hardware.get('gpu', {}).get('vram_gb', 'N/A')} GB VRAM)")
        lines.append("-" * 20)

        reqs = data.get('requirements', {})
        lines.append("  Requirements:")
        for package, version in reqs.items():
            lines.append(f"    - {package}: {version}")

        lines.append("--- End of Information ---\n")

        return "\n".join(lines)


if __name__ == '__main__':
    # Bloque de prueba para ejecución directa del script
    current_file_path = Path(__file__).resolve()
    project_root_dir = current_file_path.parent.parent.parent

    # Crear archivos de prueba si no existen para asegurar que el script se puede ejecutar
    version_file_path = project_root_dir / "nexi.version"
    if not version_file_path.exists():
        print("Creando nexi.version de prueba...")
        with open(version_file_path, "w") as f:
            json.dump({"nexi_version": "1.6.0.0-dev"}, f, indent=2)
            
    # Borrar el info.json viejo para asegurar que se regenere con la estructura correcta
    if (project_root_dir / "info.json").exists():
        print("Eliminando info.json antiguo para regeneración...")
        (project_root_dir / "info.json").unlink()

    if not (project_root_dir / "requirements.txt").exists():
        print("Creando requirements.txt de prueba...")
        with open(project_root_dir / "requirements.txt", "w") as f:
            f.write("PySide6==6.7.0\npsutil==5.9.8\nWMI==1.5.1\n")

    # Iniciar logging y ejecutar la lógica principal
    log.start_session("system_info_test")
    updater = SystemInfo(project_root=project_root_dir)
    system_report = updater.get_info()
    log.info(system_report)

    print(f"\nProceso finalizado. Revisa el archivo '{project_root_dir / 'info.json'}' y la salida del log.")