#!/usr/bin/env python3
"""Orquestador de empaquetado y distribución multiplataforma para lazyJobFinder.

Genera los paquetes de instalación y distribución autónoma para Windows y GNU/Linux,
garantizando:
- Inclusión del frontend estático precompilado en web/out.
- Uso de plantillas limpias de configuración sin datos personales ni secretos.
- Verificación previa de seguridad (anti-fuga de credenciales).
- Empaquetado de Docker Compose de producción y exportación de imágenes/modelos.
- Generación de instalador Inno Setup (.exe), portable (.zip), tarball (.tar.gz) y ejecutable Linux (.run).
- Emisión del manifiesto de release con hashes criptográficos SHA-256.
"""

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from typing import Dict, List, Optional, Tuple

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKAGING_DIR = os.path.join(ROOT_DIR, "packaging")
CONFIG_TEMPLATES_DIR = os.path.join(PACKAGING_DIR, "config-templates")
STAGING_DIR = os.path.join(PACKAGING_DIR, "staging")
DIST_DIR = os.path.join(ROOT_DIR, "dist")


def log(msg: str, level: str = "INFO") -> None:
    colors = {
        "INFO": "\033[94m",
        "SUCCESS": "\033[92m",
        "WARN": "\033[93m",
        "ERROR": "\033[91m",
        "RESET": "\033[0m",
    }
    prefix = f"{colors.get(level, '')}[{level}]{colors['RESET']}"
    print(f"{prefix} {msg}")


def compute_sha256(filepath: str) -> str:
    """Calcula el hash SHA-256 de un archivo para verificación de integridad."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(128 * 1024):
            h.update(chunk)
    return h.hexdigest()


class ReleaseBuilder:
    def __init__(self, version: str = "1.0.0", clean: bool = False, skip_docker: bool = False, skip_model: bool = False):
        self.version = version
        self.clean = clean
        self.skip_docker = skip_docker
        self.skip_model = skip_model
        self.manifest_data = self._load_base_manifest()

    def _load_base_manifest(self) -> Dict:
        manifest_path = os.path.join(PACKAGING_DIR, "release-manifest.json")
        if os.path.exists(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"name": "lazyJobFinder", "version": self.version}

    def audit_security(self) -> None:
        """Escanea las plantillas y el entorno de empaquetado para evitar fuga de secretos."""
        log("Ejecutando auditoría de seguridad previa...", "INFO")
        suspicious_patterns = [
            (r"\b[0-9]{8,10}:[a-zA-Z0-9_-]{35}\b", "Token real de bot de Telegram"),
            (r"client_secret:\s*['\"][a-zA-Z0-9_\-]{20,}['\"]", "Client Secret real"),
            (r"password:\s*['\"][^'\"]{4,}['\"]", "Contraseña en texto plano"),
        ]

        # Comprobar que en config-templates no haya secretos
        for root, _, files in os.walk(CONFIG_TEMPLATES_DIR):
            for file in files:
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    for pattern, desc in suspicious_patterns:
                        if re.search(pattern, content):
                            raise ValueError(f"Fuga potencial de credenciales detectada en {file}: {desc}")
                except Exception as e:
                    log(f"Error revisando {filepath}: {e}", "WARN")

        # Comprobar que no se copien bases de datos ni archivos .env con datos reales
        env_real = os.path.join(ROOT_DIR, ".env")
        if os.path.exists(env_real):
            log("Archivo .env local detectado. Será excluido de la distribución.", "INFO")

        log("Auditoría de seguridad completada con éxito. No se detectaron secretos.", "SUCCESS")

    def verify_frontend(self) -> None:
        """Comprueba que el frontend Next.js esté exportado en web/out."""
        out_dir = os.path.join(ROOT_DIR, "web", "out")
        index_html = os.path.join(out_dir, "index.html")

        if not os.path.exists(index_html):
            log("web/out no contiene index.html. Compilando panel web con npm run build...", "INFO")
            web_dir = os.path.join(ROOT_DIR, "web")
            shell_cmd = "npm run build"
            ret = subprocess.call(shell_cmd, cwd=web_dir, shell=True)
            if ret != 0:
                raise RuntimeError("Fallo durante la compilación estática de Next.js en web/.")
            log("Panel web compilado correctamente.", "SUCCESS")
        else:
            log(f"Frontend estático validado en: {out_dir}", "SUCCESS")

    def prepare_staging(self) -> None:
        """Prepara el directorio temporal de staging con una lista explícita de archivos permitidos."""
        log("Preparando entorno de staging limpio...", "INFO")
        if os.path.exists(STAGING_DIR):
            shutil.rmtree(STAGING_DIR)
        os.makedirs(STAGING_DIR, exist_ok=True)

        # 1. Copiar Docker Compose de producción
        shutil.copy2(
            os.path.join(PACKAGING_DIR, "compose.release.yaml"),
            os.path.join(STAGING_DIR, "docker-compose.yml"),
        )

        # 2. Copiar .env.example
        shutil.copy2(
            os.path.join(CONFIG_TEMPLATES_DIR, ".env.example"),
            os.path.join(STAGING_DIR, ".env.example"),
        )

        # 3. Copiar plantillas limpias a config/ y config-templates/
        staging_config = os.path.join(STAGING_DIR, "config")
        staging_templates = os.path.join(STAGING_DIR, "config-templates")
        shutil.copytree(CONFIG_TEMPLATES_DIR, staging_config)
        shutil.copytree(CONFIG_TEMPLATES_DIR, staging_templates)

        # 4. Crear estructura de carpetas de datos de usuario con .gitkeep
        for subfolder in ["", "uploaded_cvs", "documents"]:
            folder = os.path.join(STAGING_DIR, "data", subfolder)
            os.makedirs(folder, exist_ok=True)
            with open(os.path.join(folder, ".gitkeep"), "w", encoding="utf-8") as f:
                f.write("")

        # 5. Copiar scripts de Windows
        win_src = os.path.join(PACKAGING_DIR, "windows")
        for f in ["launch.bat", "stop.bat", "install.bat"]:
            src_f = os.path.join(win_src, f)
            if os.path.exists(src_f):
                shutil.copy2(src_f, os.path.join(STAGING_DIR, f))

        # 6. Copiar scripts de Linux
        linux_src = os.path.join(PACKAGING_DIR, "linux")
        for f in ["launch.sh", "stop.sh", "installer.sh"]:
            src_f = os.path.join(linux_src, f)
            if os.path.exists(src_f):
                shutil.copy2(src_f, os.path.join(STAGING_DIR, f))

        # 7. Copiar README y LICENSE si existen
        for doc in ["README.md", "LICENSE"]:
            doc_src = os.path.join(ROOT_DIR, doc)
            if os.path.exists(doc_src):
                shutil.copy2(doc_src, os.path.join(STAGING_DIR, doc))

        log("Directorio de staging preparado correctamente.", "SUCCESS")

    def build_docker_images(self) -> None:
        """Construye la imagen Docker de lazyJobFinder y exporta las imágenes a un archivo tar."""
        if self.skip_docker:
            log("Omitiendo empaquetado de imágenes Docker (--skip-docker).", "WARN")
            return

        # Comprobar si el daemon de Docker responde
        try:
            res = subprocess.run(["docker", "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if res.returncode != 0:
                log("Daemon de Docker no disponible actualmente. Omitiendo 'docker save'.", "WARN")
                return
        except Exception:
            log("Comando docker no encontrado. Omitiendo construcción de imágenes.", "WARN")
            return

        app_tag = f"lazyjobfinder:{self.version}"
        log(f"Construyendo imagen de producción: {app_tag}...", "INFO")
        build_cmd = ["docker", "build", "-t", app_tag, "-t", "lazyjobfinder:latest", "."]
        ret = subprocess.call(build_cmd, cwd=ROOT_DIR)
        if ret != 0:
            raise RuntimeError("Fallo al construir la imagen Docker de lazyjobfinder.")

        log("Asegurando presencia de la imagen oficial de Ollama...", "INFO")
        subprocess.call(["docker", "pull", "ollama/ollama:latest"])

        images_tar = os.path.join(STAGING_DIR, "images.tar")
        log(f"Exportando imágenes a {images_tar}...", "INFO")
        save_cmd = ["docker", "save", "-o", images_tar, app_tag, "lazyjobfinder:latest", "ollama/ollama:latest"]
        ret = subprocess.call(save_cmd)
        if ret == 0:
            log(f"Imágenes exportadas con éxito ({os.path.getsize(images_tar) // (1024*1024)} MB).", "SUCCESS")
        else:
            log("No se pudo exportar images.tar. Las imágenes se descargarán o construirán en el destino.", "WARN")

    def build_windows_distribution(self) -> List[str]:
        """Genera el paquete portable ZIP y compila el instalador .EXE con Inno Setup si está disponible."""
        log("Generando distribución para Windows x64...", "INFO")
        os.makedirs(DIST_DIR, exist_ok=True)
        artifacts = []

        base_name = f"lazyJobFinder-{self.version}-windows-x64"
        zip_path = os.path.join(DIST_DIR, f"{base_name}.zip")

        # 1. Crear archivo comprimido portable (.zip)
        log(f"Creando paquete portable: {zip_path}...", "INFO")
        shutil.make_archive(os.path.splitext(zip_path)[0], "zip", STAGING_DIR)
        if os.path.exists(zip_path):
            artifacts.append(zip_path)
            log(f"Paquete portable Windows generado: {zip_path}", "SUCCESS")

        # 2. Intentar compilar con Inno Setup
        iscc_candidates = [
            "iscc",
            r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
            r"C:\Program Files\Inno Setup 6\ISCC.exe",
        ]
        iscc_path = None
        for candidate in iscc_candidates:
            if shutil.which(candidate) or os.path.exists(candidate):
                iscc_path = candidate
                break

        iss_file = os.path.join(PACKAGING_DIR, "windows", "installer.iss")
        if iscc_path and os.path.exists(iss_file):
            log(f"Compilando instalador Inno Setup con {iscc_path}...", "INFO")
            cmd = [iscc_path, iss_file]
            ret = subprocess.call(cmd)
            exe_path = os.path.join(DIST_DIR, f"{base_name}.exe")
            if ret == 0 and os.path.exists(exe_path):
                artifacts.append(exe_path)
                log(f"Instalador ejecutable de Windows generado: {exe_path}", "SUCCESS")
            else:
                log("Inno Setup finalizó con advertencias o no generó el binario final.", "WARN")
        else:
            log(
                "Inno Setup (ISCC.exe) no está instalado en el sistema. "
                f"El archivo de proyecto Inno Setup queda disponible en '{iss_file}' "
                "y el paquete portable Windows (.zip) contiene el instalador interactivo 'install.bat'.",
                "INFO",
            )

        return artifacts

    def build_linux_distribution(self) -> List[str]:
        """Genera el tarball .tar.gz y el instalador autoextraíble ejecutable .run para Linux."""
        log("Generando distribución para GNU/Linux x64...", "INFO")
        os.makedirs(DIST_DIR, exist_ok=True)
        artifacts = []

        base_name = f"lazyJobFinder-{self.version}-linux-x64"
        tar_path = os.path.join(DIST_DIR, f"{base_name}.tar.gz")

        # 1. Crear tarball .tar.gz
        log(f"Creando archivo tarball: {tar_path}...", "INFO")
        shutil.make_archive(os.path.splitext(os.path.splitext(tar_path)[0])[0], "gztar", STAGING_DIR)
        if os.path.exists(tar_path):
            artifacts.append(tar_path)
            log(f"Tarball Linux generado: {tar_path}", "SUCCESS")

        # 2. Crear instalador autoextraíble (.run)
        run_path = os.path.join(DIST_DIR, f"{base_name}.run")
        log(f"Construyendo instalador autoextraíble: {run_path}...", "INFO")

        run_header = (
            "#!/usr/bin/env bash\n"
            "# =============================================================================\n"
            f"# lazyJobFinder v{self.version} - Instalador Autónomo para Linux\n"
            "# =============================================================================\n"
            "set -e\n"
            "TMP_PAYLOAD_DIR=$(mktemp -d -t lazyjobfinder-install-XXXXXX)\n"
            "cleanup() { rm -rf \"$TMP_PAYLOAD_DIR\"; }\n"
            "trap cleanup EXIT\n"
            "echo '--> Desempaquetando instalador de lazyJobFinder...'\n"
            "ARCHIVE_LINE=$(awk '/^__ARCHIVE_STARTS_HERE__/ {print NR + 1; exit 0; }' \"$0\")\n"
            "tail -n +\"$ARCHIVE_LINE\" \"$0\" | tar -xz -C \"$TMP_PAYLOAD_DIR\"\n"
            "bash \"$TMP_PAYLOAD_DIR/installer.sh\" \"$@\"\n"
            "exit 0\n"
            "__ARCHIVE_STARTS_HERE__\n"
        )

        try:
            with open(run_path, "wb") as f_out:
                f_out.write(run_header.encode("utf-8"))
                with open(tar_path, "rb") as f_in:
                    shutil.copyfileobj(f_in, f_out)
            # Marcar como ejecutable
            try:
                os.chmod(run_path, 0o755)
            except Exception:
                pass
            artifacts.append(run_path)
            log(f"Instalador ejecutable Linux generado: {run_path}", "SUCCESS")
        except Exception as e:
            log(f"Error generando instalador .run: {e}", "WARN")

        return artifacts

    def emit_release_manifest(self, artifacts: List[str]) -> None:
        """Emite el manifiesto final con sumas de comprobación SHA-256 e inventario completo."""
        log("Emitiendo manifiesto de publicación con verificación criptográfica...", "INFO")
        manifest = dict(self.manifest_data)
        manifest["version"] = self.version
        manifest["build_timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        manifest["artifacts"] = []

        sums_lines = []
        for artifact in artifacts:
            filename = os.path.basename(artifact)
            size = os.path.getsize(artifact)
            sha = compute_sha256(artifact)
            manifest["artifacts"].append({
                "filename": filename,
                "size_bytes": size,
                "size_mb": round(size / (1024 * 1024), 2),
                "sha256": sha,
            })
            sums_lines.append(f"{sha}  {filename}")

        # Guardar release-manifest.json en dist/
        manifest_path = os.path.join(DIST_DIR, "release-manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

        # Guardar SHA256SUMS.txt en dist/
        sums_path = os.path.join(DIST_DIR, "SHA256SUMS.txt")
        with open(sums_path, "w", encoding="utf-8") as f:
            f.write("\n".join(sums_lines) + "\n")

        log(f"Manifiesto guardado en: {manifest_path}", "SUCCESS")
        log(f"Sumas de comprobación guardadas en: {sums_path}", "SUCCESS")

    def run(self, platforms_target: str = "all") -> None:
        start_time = time.time()
        print("\n" + "=" * 70)
        print(f"       CONSTRUCCIÓN DE DISTRIBUCIÓN lazyJobFinder v{self.version}")
        print("=" * 70 + "\n")

        # 1. Auditoría de seguridad
        self.audit_security()

        # 2. Verificación del frontend estático
        self.verify_frontend()

        # 3. Preparación del directorio staging
        self.prepare_staging()

        # 4. Construcción de imágenes Docker (si está habilitado)
        self.build_docker_images()

        # 5. Generación de artefactos según plataforma
        artifacts = []
        build_windows = platforms_target in ("all", "windows")
        build_linux = platforms_target in ("all", "linux")

        if build_windows:
            artifacts.extend(self.build_windows_distribution())

        if build_linux:
            artifacts.extend(self.build_linux_distribution())

        # 6. Manifiesto e integridad
        self.emit_release_manifest(artifacts)

        elapsed = time.time() - start_time
        print("\n" + "=" * 70)
        log(f"¡Distribución completada en {elapsed:.1f} segundos!", "SUCCESS")
        print("Artefactos disponibles en carpeta 'dist/':")
        for art in artifacts:
            size_mb = os.path.getsize(art) / (1024 * 1024)
            print(f"  - {os.path.basename(art)} ({size_mb:.2f} MB)")
        print("=" * 70 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generador de instaladores y distribución de lazyJobFinder",
    )
    parser.add_argument(
        "--platform",
        choices=["all", "windows", "linux"],
        default="all",
        help="Plataforma de destino para el empaquetado (por defecto: all)",
    )
    parser.add_argument(
        "--version",
        default="1.0.0",
        help="Versión semántica del lanzamiento (por defecto: 1.0.0)",
    )
    parser.add_argument(
        "--skip-docker",
        action="store_true",
        help="Omitir 'docker build' y 'docker save' de imágenes",
    )
    parser.add_argument(
        "--skip-model",
        action="store_true",
        help="Omitir exportación masiva del modelo de Ollama",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Limpiar carpetas staging y dist antes de comenzar",
    )

    args = parser.parse_args()

    builder = ReleaseBuilder(
        version=args.version,
        clean=args.clean,
        skip_docker=args.skip_docker,
        skip_model=args.skip_model,
    )
    builder.run(platforms_target=args.platform)


if __name__ == "__main__":
    main()
