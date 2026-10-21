#!/usr/bin/env python3
"""Orquestador de empaquetado y distribución multiplataforma para lazyJobFinder.

Genera los paquetes de instalación y distribución autónoma para Windows y GNU/Linux,
garantizando:
- Contexto de construcción de Docker 100% aislado (cero riesgo de incluir datos personales).
- Inclusión del frontend estático precompilado en web/out.
- Uso exclusivo de plantillas limpias de configuración sin datos personales ni secretos.
- Auditoría estricta y bloqueante de seguridad previa (anti-fuga de credenciales).
- Empaquetado de Docker Compose de producción con soporte de versiones dinámicas.
- Empaquetado real del modelo de Ollama en el volumen persistente (o aviso explícito si se omite).
- Generación de instalador Inno Setup (.exe), portable (.zip), tarball (.tar.gz) y ejecutable Linux (.run).
- Emisión del manifiesto de release unificado con hashes criptográficos SHA-256.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import time
from typing import Any, Dict, List, Optional, Tuple
import zipfile

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKAGING_DIR = os.path.join(ROOT_DIR, "packaging")
CONFIG_TEMPLATES_DIR = os.path.join(PACKAGING_DIR, "config-templates")
STAGING_DIR = os.path.join(PACKAGING_DIR, "staging")
DIST_DIR = os.path.join(ROOT_DIR, "dist")

# Versión fijada de Ollama para reproducibilidad determinista en builds
OLLAMA_PINNED_VERSION = "0.5.7"


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
    def __init__(
        self,
        version: str = "1.0.0",
        clean: bool = False,
        skip_docker: bool = False,
        skip_model: bool = False,
        build_frontend: bool = False,
    ):
        self.version = version
        self.clean = clean
        self.skip_docker = skip_docker
        self.skip_model = skip_model
        self.build_frontend = build_frontend
        self.model_included = False
        self._staging_model_digests: Optional[List[str]] = None
        self.min_weight_blob_size_bytes: int = 500 * 1024 * 1024
        self.min_complete_artifact_size_mb: float = 1200.0
        self.manifest_data = self._load_base_manifest()

    def _load_base_manifest(self) -> Dict:
        manifest_path = os.path.join(PACKAGING_DIR, "release-manifest.json")
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                log(f"Error leyendo base manifest: {e}", "WARN")
        return {"name": "lazyJobFinder", "version": self.version}

    def audit_security(self, target_dir: str) -> None:
        """
        Escanea exhaustivamente las plantillas y el staging para evitar fuga de secretos.
        Es BLOQUEANTE: cualquier hallazgo sospechoso o error de lectura aborta la publicación.
        """
        log(f"Ejecutando auditoría de seguridad estricta en {target_dir}...", "INFO")
        suspicious_patterns = [
            (r"\b[0-9]{8,10}:[a-zA-Z0-9_-]{35}\b", "Token real de bot de Telegram"),
            (r"client_secret:\s*['\"][a-zA-Z0-9_\-]{16,}['\"]", "Client Secret real"),
            (r"password:\s*['\"][^'\"]{4,}['\"]", "Contraseña en texto plano"),
            (r"-----BEGIN (RSA|EC|OPENSSH|PRIVATE) KEY-----", "Clave privada criptográfica"),
        ]

        forbidden_filenames = [
            re.compile(r"^.*\.db(-wal|-shm)?$", re.IGNORECASE),
            re.compile(r"^.*\.sqlite(3)?$", re.IGNORECASE),
            re.compile(r"^secrets\.json$", re.IGNORECASE),
            re.compile(r"^\.env$", re.IGNORECASE),  # .env real nunca se distribuye, solo .env.example
            re.compile(r"^active_cv\.json$", re.IGNORECASE),
        ]

        for root, _, files in os.walk(target_dir):
            for file in files:
                filepath = os.path.join(root, file)
                relpath = os.path.relpath(filepath, target_dir)

                # 1. Comprobar nombres de archivos prohibidos
                for pattern in forbidden_filenames:
                    if pattern.match(file):
                        raise RuntimeError(
                            f"AUDITORÍA DE SEGURIDAD FALLIDA: Archivo prohibido detectado en la distribución: {relpath}"
                        )

                # 2. Comprobar contenido contra patrones sospechosos de credenciales
                try:
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    for pat, desc in suspicious_patterns:
                        if re.search(pat, content):
                            raise RuntimeError(
                                f"AUDITORÍA DE SEGURIDAD FALLIDA en '{relpath}': {desc}"
                            )
                except UnicodeDecodeError:
                    pass  # Archivos binarios ignorados de análisis textual
                except Exception as e:
                    if not isinstance(e, RuntimeError):
                        raise RuntimeError(f"Error auditando '{relpath}': {e}") from e
                    raise

        log("Auditoría de seguridad superada con éxito. Cero secretos detectados.", "SUCCESS")

    def verify_frontend(self) -> None:
        """Comprueba que el frontend Next.js esté exportado en web/out."""
        out_dir = os.path.join(ROOT_DIR, "web", "out")
        index_html = os.path.join(out_dir, "index.html")

        if not os.path.exists(index_html):
            if self.build_frontend:
                log("web/out no contiene index.html. Compilando panel web con npm run build...", "INFO")
                web_dir = os.path.join(ROOT_DIR, "web")
                ret = subprocess.call("npm run build", cwd=web_dir, shell=True)
                if ret != 0:
                    raise RuntimeError("Fallo durante la compilación estática de Next.js en web/.")
                log("Panel web compilado correctamente.", "SUCCESS")
            else:
                raise RuntimeError(
                    "El frontend estático no está compilado en 'web/out/index.html'.\n"
                    "Por favor ejecuta 'npm run build' en la carpeta web/ o añade el argumento '--build-frontend'."
                )
        else:
            log(f"Frontend estático validado en: {out_dir}", "SUCCESS")

    def prepare_staging(self) -> None:
        """Prepara el directorio temporal de staging con una lista explícita de archivos permitidos."""
        log("Preparando entorno de staging limpio...", "INFO")
        if os.path.exists(STAGING_DIR):
            shutil.rmtree(STAGING_DIR)
        os.makedirs(STAGING_DIR, exist_ok=True)

        # 1. Copiar Docker Compose de producción interpolando la versión del release
        compose_src = os.path.join(PACKAGING_DIR, "compose.release.yaml")
        with open(compose_src, "r", encoding="utf-8") as f:
            compose_content = f.read()

        # Sustituir etiquetas fijas por la versión dinámica actual
        compose_content = compose_content.replace(
            "${LAZYJOB_IMAGE:-lazyjobfinder:latest}",
            f"lazyjobfinder:{self.version}",
        )
        with open(os.path.join(STAGING_DIR, "docker-compose.yml"), "w", encoding="utf-8") as f:
            f.write(compose_content)

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

        # 8. Identificar tipo de distribución (ligera o completa)
        light_marker = os.path.join(STAGING_DIR, ".light_release")
        if self.skip_docker or self.skip_model:
            with open(light_marker, "w", encoding="utf-8") as f:
                f.write(f"lazyJobFinder {self.version} Lightweight Distribution\n")
                f.write(f"skip_docker={self.skip_docker}\nskip_model={self.skip_model}\n")
            log("Marcador de distribución ligera (.light_release) generado en staging.", "INFO")
        elif os.path.exists(light_marker):
            os.remove(light_marker)

        # Ejecutar auditoría bloqueante sobre el staging resultante
        self.audit_security(STAGING_DIR)
        log("Directorio de staging preparado y auditado correctamente.", "SUCCESS")

    def build_docker_images(self) -> None:
        """
        Construye la imagen Docker de lazyJobFinder desde un CONTEXTO TOTALMENTE AISLADO.
        Garantiza que ningún archivo personal o de desarrollo pueda filtrarse a la imagen.
        """
        if self.skip_docker:
            log("Omitiendo empaquetado de imágenes Docker (--skip-docker).", "WARN")
            return

        try:
            res = subprocess.run(["docker", "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if res.returncode != 0:
                log("Daemon de Docker no disponible actualmente. Omitiendo construcción de imágenes.", "WARN")
                return
        except Exception:
            log("Comando docker no encontrado. Omitiendo construcción de imágenes.", "WARN")
            return

        # 1. Crear contexto de compilación aislado
        isolated_context = os.path.join(PACKAGING_DIR, "staging_build_context")
        if os.path.exists(isolated_context):
            shutil.rmtree(isolated_context)
        os.makedirs(isolated_context, exist_ok=True)

        log("Creando contexto de construcción Docker aislado (sin datos personales)...", "INFO")
        shutil.copy2(os.path.join(ROOT_DIR, "Dockerfile"), os.path.join(isolated_context, "Dockerfile"))
        shutil.copytree(
            os.path.join(ROOT_DIR, "src"),
            os.path.join(isolated_context, "src"),
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
        )

        # El directorio config dentro de la imagen contiene ÚNICAMENTE las plantillas limpias
        shutil.copytree(CONFIG_TEMPLATES_DIR, os.path.join(isolated_context, "config"))

        # El frontend compilado
        shutil.copytree(os.path.join(ROOT_DIR, "web", "out"), os.path.join(isolated_context, "web", "out"))

        app_tag = f"lazyjobfinder:{self.version}"
        log(f"Construyendo imagen de producción aislada ({app_tag}) forzando plataforma linux/amd64...", "INFO")
        build_cmd = [
            "docker", "build",
            "--platform", "linux/amd64",
            "-t", app_tag,
            "-t", "lazyjobfinder:latest",
            ".",
        ]
        ret = subprocess.call(build_cmd, cwd=isolated_context)

        # Limpiar el contexto temporal inmediatamente
        shutil.rmtree(isolated_context, ignore_errors=True)

        if ret != 0:
            raise RuntimeError("Fallo crítico al construir la imagen Docker aislada de lazyjobfinder.")

        ollama_pinned_tag = f"ollama/ollama:{OLLAMA_PINNED_VERSION}"
        log(f"Asegurando presencia de la imagen oficial de Ollama ({ollama_pinned_tag}, linux/amd64)...", "INFO")
        ret_pull = subprocess.call(["docker", "pull", "--platform", "linux/amd64", ollama_pinned_tag])
        if ret_pull != 0:
            raise RuntimeError(f"Fallo crítico al descargar la imagen base de {ollama_pinned_tag}.")

        # Etiquetar también como :latest para máxima compatibilidad
        subprocess.call(["docker", "tag", ollama_pinned_tag, "ollama/ollama:latest"])

        # 2. Exportación de imágenes a images.tar en staging
        images_tar = os.path.join(STAGING_DIR, "images.tar")
        log(f"Exportando imágenes base a {images_tar}...", "INFO")
        save_cmd = [
            "docker", "save", "-o", images_tar,
            app_tag, "lazyjobfinder:latest",
            ollama_pinned_tag, "ollama/ollama:latest",
        ]
        ret = subprocess.call(save_cmd)
        if ret != 0 or not os.path.exists(images_tar) or os.path.getsize(images_tar) < 1024 * 1024:
            raise RuntimeError("Fallo crítico: no se pudo exportar images.tar con las imágenes de lazyjobfinder y Ollama.")
        log(f"Imágenes exportadas con éxito ({os.path.getsize(images_tar) // (1024*1024)} MB).", "SUCCESS")

    def export_ollama_model(self) -> None:
        """
        Descarga y exporta EXCLUSIVAMENTE los datos del modelo qwen2.5:3b-instruct
        usando un volumen efímero dedicado y limpio, evitando empaquetar otros modelos
        presentes en el entorno del desarrollador.
        """
        log("Iniciando empaquetado aislado del modelo de IA (qwen2.5:3b-instruct)...", "INFO")
        model_tar = os.path.join(STAGING_DIR, "ollama_model.tar.gz")
        ephemeral_volume = f"lazyjob_export_model_{int(time.time())}"
        container_name = None
        volume_created = False

        try:
            # 1. Crear volumen aislado y limpio
            log(f"Creando volumen temporal limpio '{ephemeral_volume}' para descarga aislada...", "INFO")
            subprocess.run(["docker", "volume", "create", ephemeral_volume], check=True)
            volume_created = True

            # 2. Iniciar servidor Ollama temporal en segundo plano sobre el volumen limpio
            container_name = f"lazyjob_model_puller_{int(time.time())}"
            run_server_cmd = [
                "docker", "run", "-d",
                "--name", container_name,
                "-v", f"{ephemeral_volume}:/root/.ollama",
                f"ollama/ollama:{OLLAMA_PINNED_VERSION}",
                "serve",
            ]
            run_res = subprocess.run(run_server_cmd, capture_output=True, text=True)
            if run_res.returncode != 0:
                raise RuntimeError(f"Fallo al iniciar contenedor de exportación de Ollama: {run_res.stderr}")

            # Esperar a que el servidor Ollama esté listo
            log("Esperando inicialización del servidor Ollama temporal...", "INFO")
            ready = False
            for _ in range(15):
                time.sleep(2)
                check_cmd = ["docker", "exec", container_name, "ollama", "list"]
                check_res = subprocess.run(check_cmd, capture_output=True, text=True)
                if check_res.returncode == 0:
                    ready = True
                    break

            if not ready:
                raise RuntimeError("El servidor temporal de Ollama no respondió a tiempo.")

            # 3. Descargar el modelo requerido qwen2.5:3b-instruct
            log("Descargando modelo oficial qwen2.5:3b-instruct en el volumen limpio...", "INFO")
            pull_cmd = ["docker", "exec", container_name, "ollama", "pull", "qwen2.5:3b-instruct"]
            pull_res = subprocess.run(pull_cmd)
            if pull_res.returncode != 0:
                raise RuntimeError("Fallo durante 'ollama pull qwen2.5:3b-instruct' en el contenedor temporal.")

            # 4. Verificar mediante 'ollama list' que el modelo está registrado
            verify_cmd = ["docker", "exec", container_name, "ollama", "list"]
            verify_res = subprocess.run(verify_cmd, capture_output=True, text=True)
            if "qwen2.5:3b-instruct" not in verify_res.stdout:
                raise RuntimeError(
                    f"El modelo qwen2.5:3b-instruct no aparece en 'ollama list': {verify_res.stdout}"
                )
            log("Modelo qwen2.5:3b-instruct verificado en 'ollama list'.", "SUCCESS")

            # 4.1 Extraer y registrar los digests de referencia independientes de qwen2.5:3b-instruct directamente del contenedor
            read_mf_cmd = [
                "docker", "exec", container_name,
                "cat", "/root/.ollama/models/manifests/registry.ollama.ai/library/qwen2.5/3b-instruct",
            ]
            mf_res = subprocess.run(read_mf_cmd, capture_output=True, text=True)
            if mf_res.returncode != 0 or not mf_res.stdout:
                raise RuntimeError(
                    f"Fallo crítico: No se pudo leer el manifiesto canónico de 'qwen2.5:3b-instruct' del contenedor: {mf_res.stderr.strip()}"
                )
            try:
                mf_data = json.loads(mf_res.stdout)
                ref_digests = []
                if "config" in mf_data and "digest" in mf_data["config"]:
                    ref_digests.append(mf_data["config"]["digest"].replace("sha256:", "").replace("sha256-", "").strip().lower())
                for lyr in mf_data.get("layers", []):
                    if "digest" in lyr:
                        ref_digests.append(lyr["digest"].replace("sha256:", "").replace("sha256-", "").strip().lower())
                if not ref_digests:
                    raise RuntimeError("El manifiesto de qwen2.5:3b-instruct en el contenedor no contiene capas ni digests válidos.")
                self._staging_model_digests = ref_digests
                log(f"Referencia independiente de 'qwen2.5:3b-instruct' capturada del contenedor ({len(ref_digests)} digests).", "SUCCESS")
            except Exception as exc:
                raise RuntimeError(
                    f"Fallo crítico al validar el manifiesto independiente de 'qwen2.5:3b-instruct' desde el contenedor: {exc}"
                )

            # 5. Detener el contenedor de servicio para volcar los datos a salvo
            subprocess.run(["docker", "stop", "-t", "5", container_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["docker", "rm", "-f", container_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            container_name = None

            # 6. Exportar los datos usando la imagen de ollama (que ya incluye tar) para no depender de alpine
            log(f"Exportando datos limpios del modelo a {model_tar}...", "INFO")
            export_cmd = [
                "docker", "run", "--rm",
                "-v", f"{ephemeral_volume}:/source_ollama:ro",
                "-v", f"{STAGING_DIR}:/backup",
                "--entrypoint", "/bin/sh",
                f"ollama/ollama:{OLLAMA_PINNED_VERSION}",
                "-c",
                "tar czf /backup/ollama_model.tar.gz -C /source_ollama .",
            ]
            exp_ret = subprocess.call(export_cmd)
            if exp_ret != 0 or not os.path.exists(model_tar) or os.path.getsize(model_tar) < 500 * 1024 * 1024:
                raise RuntimeError(
                    "Fallo al comprimir ollama_model.tar.gz o el tamaño del modelo es sospechosamente pequeño."
                )

            self.model_included = True
            size_mb = os.path.getsize(model_tar) / (1024 * 1024)
            log(f"Modelo IA empaquetado con éxito: ollama_model.tar.gz ({size_mb:.1f} MB).", "SUCCESS")

        finally:
            # Limpiar contenedor si quedó instanciado
            if container_name:
                subprocess.run(["docker", "rm", "-f", container_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            # Limpiar volumen efímero solo si se creó
            if volume_created:
                subprocess.run(["docker", "volume", "rm", "-f", ephemeral_volume], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

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
            cmd = [iscc_path, f"/DMyAppVersion={self.version}", iss_file]
            ret = subprocess.call(cmd)
            exe_path = os.path.join(DIST_DIR, f"{base_name}.exe")
            if ret == 0 and os.path.exists(exe_path):
                artifacts.append(exe_path)
                log(f"Instalador ejecutable de Windows generado: {exe_path}", "SUCCESS")
            else:
                log("Inno Setup finalizó con advertencias.", "WARN")
        else:
            log(
                "Inno Setup (ISCC.exe) no está instalado en el sistema. "
                "El paquete portable Windows (.zip) contiene el instalador autónomo 'install.bat'.",
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
            try:
                os.chmod(run_path, 0o755)
            except Exception:
                pass
            artifacts.append(run_path)
            log(f"Instalador ejecutable Linux generado: {run_path}", "SUCCESS")
        except Exception as e:
            log(f"Error generando instalador .run: {e}", "WARN")

        return artifacts

    def _extract_and_hash_member_from_archive(self, archive_path: str, target_filename: str) -> str:
        """Calcula el hash SHA-256 de un miembro anidado dentro de un archivo ZIP, TAR.GZ o RUN sin escribirlo en disco.
        Lanza RuntimeError si no se encuentra o no se puede leer.
        """
        h = hashlib.sha256()
        found = False
        try:
            if archive_path.endswith(".zip"):
                with zipfile.ZipFile(archive_path, "r") as zf:
                    for name in zf.namelist():
                        if os.path.basename(name) == target_filename:
                            with zf.open(name, "r") as mf:
                                while chunk := mf.read(256 * 1024):
                                    h.update(chunk)
                            found = True
                            return h.hexdigest()
            elif archive_path.endswith(".tar.gz"):
                with tarfile.open(archive_path, "r:gz") as tf:
                    for member in tf.getmembers():
                        if os.path.basename(member.name) == target_filename:
                            f = tf.extractfile(member)
                            if f:
                                while chunk := f.read(256 * 1024):
                                    h.update(chunk)
                                found = True
                                return h.hexdigest()
            elif archive_path.endswith(".run"):
                with open(archive_path, "rb") as rf:
                    content = rf.read()
                marker = b"__ARCHIVE_STARTS_HERE__\n"
                pos = content.find(marker)
                if pos == -1:
                    raise RuntimeError(f"El instalador .run '{archive_path}' carece del marcador de archivo.")
                tar_bytes = content[pos + len(marker):]
                import io
                with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:gz") as tf:
                    for member in tf.getmembers():
                        if os.path.basename(member.name) == target_filename:
                            f = tf.extractfile(member)
                            if f:
                                while chunk := f.read(256 * 1024):
                                    h.update(chunk)
                                found = True
                                return h.hexdigest()
        except Exception as e:
            raise RuntimeError(f"Error extrayendo y calculando hash de '{target_filename}' en '{archive_path}': {e}") from e

        if not found:
            raise RuntimeError(f"Componente anidado obligatorio '{target_filename}' no encontrado en '{archive_path}'.")
        return h.hexdigest()

    def _audit_docker_layers(self, images_tar_path: str) -> None:
        """
        Inspecciona exhaustivamente el contenido de las capas internas (layer.tar o blobs) de images.tar.
        Extrae en memoria cada sub-archivo y analiza nombres y contenido de ficheros de configuración.
        No oculta excepciones de seguridad y abarca archivos textuales sin límite restrictivo de tamaño.
        """
        log("  -> Ejecutando inspección exhaustiva de capas internas en images.tar...", "INFO")
        forbidden_filenames = [
            re.compile(r"^.*\.db(-wal|-shm)?$", re.IGNORECASE),
            re.compile(r"^.*\.sqlite(3)?$", re.IGNORECASE),
            re.compile(r"^secrets\.json$", re.IGNORECASE),
            re.compile(r"^\.env$", re.IGNORECASE),
            re.compile(r"^active_cv\.json$", re.IGNORECASE),
            re.compile(r"^cv_base\.md$", re.IGNORECASE),
            re.compile(r"^.*\.pem$", re.IGNORECASE),
            re.compile(r"^.*\.key$", re.IGNORECASE),
        ]
        suspicious_patterns = [
            (r"\b[0-9]{8,10}:[a-zA-Z0-9_-]{35}\b", "Token real de bot de Telegram"),
            (r"client_secret:\s*['\"][a-zA-Z0-9_\-]{16,}['\"]", "Client Secret real"),
            (r"password:\s*['\"][^'\"]{4,}['\"]", "Contraseña en texto plano"),
            (r"-----BEGIN (RSA|EC|OPENSSH|PRIVATE) KEY-----", "Clave privada criptográfica"),
        ]

        layers_count = 0
        files_count = 0

        with tarfile.open(images_tar_path, "r") as main_tar:
            members_by_name = {m.name.replace("\\", "/"): m for m in main_tar.getmembers()}

            # 1. Obtener lista de capas obligatorias desde manifest.json
            manifest_candidates = ["manifest.json", "./manifest.json"]
            manifest_member = None
            for cand in manifest_candidates:
                if cand in members_by_name:
                    manifest_member = members_by_name[cand]
                    break

            expected_layers: List[str] = []
            if manifest_member:
                mf = main_tar.extractfile(manifest_member)
                if not mf:
                    raise RuntimeError("AUDITORÍA DE CAPAS DOCKER FALLIDA: No se pudo leer 'manifest.json' de images.tar.")
                try:
                    manifest_data = json.loads(mf.read().decode("utf-8"))
                    if isinstance(manifest_data, list):
                        for img in manifest_data:
                            for lyr in img.get("Layers", []):
                                norm_lyr = lyr.replace("\\", "/")
                                if norm_lyr not in expected_layers:
                                    expected_layers.append(norm_lyr)
                except Exception as exc:
                    raise RuntimeError(f"AUDITORÍA DE CAPAS DOCKER FALLIDA: 'manifest.json' corrupto o inválido: {exc}")

            if not manifest_member:
                raise RuntimeError("AUDITORÍA DE CAPAS DOCKER FALLIDA: 'images.tar' no contiene el archivo canónico 'manifest.json' de Docker save.")

            if not expected_layers:
                raise RuntimeError("AUDITORÍA DE CAPAS DOCKER FALLIDA: 'manifest.json' en 'images.tar' no define ninguna capa obligatoria ('Layers').")

            # 2. Inspeccionar obligatoriamente cada capa (sin omitir fallos de lectura)
            for layer_name in expected_layers:
                clean_layer = layer_name.lstrip("./")
                layer_member = members_by_name.get(layer_name) or members_by_name.get(f"./{clean_layer}") or members_by_name.get(clean_layer)

                if not layer_member:
                    raise RuntimeError(
                        f"AUDITORÍA DE CAPAS DOCKER FALLIDA: La capa obligatoria '{layer_name}' especificada en manifest.json no existe en images.tar."
                    )

                layer_stream = main_tar.extractfile(layer_member)
                if not layer_stream:
                    raise RuntimeError(
                        f"AUDITORÍA DE CAPAS DOCKER FALLIDA: No se pudo extraer el flujo de datos de la capa '{layer_name}'."
                    )

                try:
                    with tarfile.open(fileobj=layer_stream, mode="r:*") as layer_tar:
                        layers_count += 1
                        for sub in layer_tar.getmembers():
                            files_count += 1
                            sub_name = os.path.basename(sub.name)

                            # 1. Validar nombre de archivo
                            for pat in forbidden_filenames:
                                if pat.match(sub_name):
                                    raise RuntimeError(
                                        f"AUDITORÍA DE CAPAS DOCKER BLOQUEADA: Archivo prohibido '{sub.name}' detectado dentro de la capa '{layer_name}' de images.tar."
                                    )

                            # 2. Validar contenido en archivos no binarios
                            if sub.isfile() and sub.size > 0:
                                sf = layer_tar.extractfile(sub)
                                if not sf:
                                    continue

                                # Lectura de muestra inicial para discernir binarios de texto
                                try:
                                    sample = sf.read(1024)
                                    if b"\x00" in sample:
                                        # Archivo binario (ejecutable, biblioteca, imagen), se omite análisis textual
                                        continue
                                    # Archivo textual: leer completo y decodificar
                                    sf.seek(0)
                                    text_content = sf.read().decode("utf-8", errors="ignore")
                                except (IOError, OSError) as read_err:
                                    log(f"Aviso leyendo archivo '{sub.name}' en capa '{layer_name}': {read_err}", "WARN")
                                    continue

                                # Evaluación de patrones sospechosos (Cualquier fallo se propaga)
                                for p, desc in suspicious_patterns:
                                    if re.search(p, text_content):
                                        raise RuntimeError(
                                            f"AUDITORÍA DE CAPAS DOCKER BLOQUEADA en '{sub.name}' (capa '{layer_name}'): {desc}"
                                        )
                except Exception as layer_err:
                    if isinstance(layer_err, RuntimeError):
                        raise
                    raise RuntimeError(
                        f"AUDITORÍA DE CAPAS DOCKER FALLIDA: Error al abrir o inspeccionar la capa obligatoria '{layer_name}': {layer_err}"
                    )

        log(f"  -> Capas Docker inspeccionadas: {layers_count} capas y {files_count} archivos verificados limpios de secretos.", "SUCCESS")

    def _audit_ollama_model_archive(self, model_tar_path: str) -> None:
        """
        Verifica la estructura real del archivo tarball del modelo de Ollama:
        1. Comprueba la ruta canónica y etiqueta exacta del manifiesto de qwen2.5:3b-instruct (rechazando coincidencias aproximadas).
        2. Valida el esquema formal del manifiesto (schemaVersion, mediaType, config, layers).
        3. Exige que los digests no estén vacíos y tengan formato SHA-256 válido.
        4. Calcula y valida el hash SHA-256 criptográfico real del contenido de cada blob contra su digest.
        5. Exige la presencia del blob principal de pesos neuronales (> 500 MB).
        """
        log("  -> Validando estructura interna, manifiesto y SHA-256 de blobs reales en ollama_model.tar.gz...", "INFO")
        with tarfile.open(model_tar_path, "r:gz") as mtf:
            model_members = {m.name.replace("\\", "/"): m for m in mtf.getmembers()}
            member_names = list(model_members.keys())

            has_manifests = any("manifests" in m for m in member_names)
            has_blobs = any("blobs" in m for m in member_names)
            if not has_manifests or not has_blobs:
                raise RuntimeError(
                    "AUDITORÍA DE MODELO FALLIDA: 'ollama_model.tar.gz' no contiene las carpetas estándar 'manifests' y 'blobs'."
                )

            # 1. Localizar los manifiestos exactos '3b-instruct' y 'latest'
            regex_3b = re.compile(
                r"^(?:root/\.ollama/models/)?manifests/registry\.ollama\.ai/library/qwen2\.5/(?:3b-instruct|3b)$"
            )
            regex_latest = re.compile(
                r"^(?:root/\.ollama/models/)?manifests/registry\.ollama\.ai/library/qwen2\.5/latest$"
            )

            path_3b = None
            path_latest = None
            for name in member_names:
                clean_name = name.lstrip("./")
                if regex_3b.match(clean_name):
                    path_3b = name
                elif regex_latest.match(clean_name):
                    path_latest = name

            if not path_3b and not path_latest:
                raise RuntimeError(
                    "AUDITORÍA DE MODELO FALLIDA: No se encontró el manifiesto para 'qwen2.5:3b-instruct' en 'ollama_model.tar.gz'. "
                    "Se rechazan etiquetas y modelos no autorizados."
                )

            # Función auxiliar para extraer y validar formalmente un manifiesto
            def _parse_and_validate_manifest(path: str) -> Tuple[Dict[str, Any], List[str]]:
                f = mtf.extractfile(path)
                if not f:
                    raise RuntimeError(f"No se pudo leer el archivo de manifiesto: {path}")
                try:
                    data = json.loads(f.read().decode("utf-8"))
                except Exception as exc:
                    raise RuntimeError(f"AUDITORÍA DE MODELO FALLIDA: Manifiesto '{path}' no es JSON válido: {exc}")

                if not isinstance(data, dict):
                    raise RuntimeError(f"AUDITORÍA DE MODELO FALLIDA: Manifiesto '{path}' no contiene un objeto JSON.")
                if str(data.get("schemaVersion")) not in ("2", "2.0"):
                    raise RuntimeError(f"AUDITORÍA DE MODELO FALLIDA: schemaVersion inválido en '{path}'.")
                if not data.get("mediaType"):
                    raise RuntimeError(f"AUDITORÍA DE MODELO FALLIDA: Falta 'mediaType' en '{path}'.")

                digests = []
                if "config" in data and "digest" in data["config"]:
                    cfg_d = data["config"]["digest"].replace("sha256:", "").replace("sha256-", "").strip().lower()
                    if re.match(r"^[a-f0-9]{64}$", cfg_d):
                        digests.append(cfg_d)
                    else:
                        raise RuntimeError(f"Digest de configuración inválido en '{path}': {cfg_d}")

                lyrs = data.get("layers", [])
                if not lyrs or not isinstance(lyrs, list):
                    raise RuntimeError(f"AUDITORÍA DE MODELO FALLIDA: '{path}' no contiene lista de capas 'layers'.")

                for lyr in lyrs:
                    if "digest" in lyr:
                        lyr_d = lyr["digest"].replace("sha256:", "").replace("sha256-", "").strip().lower()
                        if re.match(r"^[a-f0-9]{64}$", lyr_d):
                            digests.append(lyr_d)
                        else:
                            raise RuntimeError(f"Digest de capa inválido en '{path}': {lyr_d}")

                if not digests:
                    raise RuntimeError(f"AUDITORÍA DE MODELO FALLIDA: Manifiesto '{path}' no contiene capas ni digests válidos.")
                return data, digests

            # Caso 1: Si existen ambos manifiestos ('3b-instruct' y 'latest'), exigir identidad estricta de digests
            if path_3b and path_latest:
                json_3b, digests_3b = _parse_and_validate_manifest(path_3b)
                json_latest, digests_latest = _parse_and_validate_manifest(path_latest)
                if digests_3b != digests_latest:
                    raise RuntimeError(
                        f"AUDITORÍA DE MODELO FALLIDA: Conflicto entre manifiestos '{path_3b}' y '{path_latest}'. "
                        "La etiqueta 'latest' no apunta al mismo modelo exacto que '3b-instruct'."
                    )
                if self._staging_model_digests and digests_3b != self._staging_model_digests:
                    raise RuntimeError(
                        f"AUDITORÍA DE MODELO FALLIDA: Los digests de '{path_3b}' difieren de los digests de referencia auditados en staging."
                    )
                exact_manifest_path = path_3b
                required_digests = digests_3b
            # Caso 2: Si solo existe '3b-instruct', es el modelo canónico exacto solicitado
            elif path_3b:
                json_3b, required_digests = _parse_and_validate_manifest(path_3b)
                if self._staging_model_digests and required_digests != self._staging_model_digests:
                    raise RuntimeError(
                        f"AUDITORÍA DE MODELO FALLIDA: Los digests de '{path_3b}' difieren de los digests de referencia auditados en staging."
                    )
                exact_manifest_path = path_3b
            # Caso 3: Si solo existe 'latest', aceptarla únicamente si sus digests coinciden con los del modelo canónico
            # de 'qwen2.5:3b-instruct' descargado y auditado previamente durante el empaquetado.
            # Si no se puede establecer esa referencia independiente previa, rechazarla de inmediato.
            else:
                json_latest, digests_latest = _parse_and_validate_manifest(path_latest)
                if not self._staging_model_digests:
                    raise RuntimeError(
                        f"AUDITORÍA DE MODELO FALLIDA: El archivo contiene únicamente '{path_latest}'. "
                        "No se puede aceptar la etiqueta 'latest' sin una referencia independiente previa de 'qwen2.5:3b-instruct'."
                    )
                if digests_latest != self._staging_model_digests:
                    raise RuntimeError(
                        f"AUDITORÍA DE MODELO FALLIDA: El manifiesto '{path_latest}' no coincide con los digests de referencia de 'qwen2.5:3b-instruct'."
                    )
                exact_manifest_path = path_latest
                required_digests = digests_latest

            # Conservar referencia para validaciones cruzadas entre staging y artefactos finales (procedente de 3b-instruct)
            if not self._staging_model_digests:
                self._staging_model_digests = required_digests

            # 2. Resolución canónica exacta de blobs (sin coincidencias parciales ambiguas)
            has_large_weight_blob = False
            for clean_digest in required_digests:
                exact_candidates = [
                    f"blobs/sha256-{clean_digest}",
                    f"blobs/sha256:{clean_digest}",
                    f"root/.ollama/models/blobs/sha256-{clean_digest}",
                    f"root/.ollama/models/blobs/sha256:{clean_digest}",
                ]
                blob_match = None
                for cand in exact_candidates:
                    if cand in model_members:
                        blob_match = model_members[cand]
                        break
                    cand_dot = f"./{cand}"
                    if cand_dot in model_members:
                        blob_match = model_members[cand_dot]
                        break

                if not blob_match:
                    # Comprobación de coincidencia exacta por nombre de archivo dentro del directorio 'blobs'
                    for bname, m in model_members.items():
                        parts = bname.lstrip("./").split("/")
                        if len(parts) >= 2 and parts[-2] == "blobs":
                            if parts[-1] in (f"sha256-{clean_digest}", f"sha256:{clean_digest}", clean_digest):
                                blob_match = m
                                break

                if not blob_match:
                    raise RuntimeError(
                        f"AUDITORÍA DE MODELO FALLIDA: El blob requerido '{clean_digest}' no se encuentra en la ruta canónica en 'ollama_model.tar.gz'."
                    )
                if blob_match.size == 0:
                    raise RuntimeError(
                        f"AUDITORÍA DE MODELO FALLIDA: El blob '{blob_match.name}' está vacío (0 bytes)."
                    )

                # Verificación criptográfica real calculando SHA-256 sobre el flujo de datos del blob
                blob_stream = mtf.extractfile(blob_match)
                if not blob_stream:
                    raise RuntimeError(f"Fallo al abrir el blob '{blob_match.name}' para verificación de hash.")
                h_blob = hashlib.sha256()
                while chunk := blob_stream.read(512 * 1024):
                    h_blob.update(chunk)
                computed_blob_sha = h_blob.hexdigest().lower()

                if computed_blob_sha != clean_digest.lower():
                    raise RuntimeError(
                        f"INTEGRIDAD CRIPTOGRÁFICA FALLIDA en '{blob_match.name}': "
                        f"SHA-256 calculado ({computed_blob_sha}) != digest esperado ({clean_digest})."
                    )

                if blob_match.size >= self.min_weight_blob_size_bytes:
                    has_large_weight_blob = True

            if not has_large_weight_blob:
                min_mb = max(1, self.min_weight_blob_size_bytes // (1024 * 1024))
                raise RuntimeError(
                    f"AUDITORÍA DE MODELO FALLIDA: 'ollama_model.tar.gz' no contiene el blob principal de pesos neuronales (>= {min_mb} MB)."
                )

            log(f"  -> Manifiesto '{exact_manifest_path}' y {len(required_digests)} blobs verificados criptográficamente (SHA-256 coincidentes).", "SUCCESS")

    def audit_final_artifacts(self, artifacts: List[str]) -> Dict[str, str]:
        """
        Audita exhaustivamente el contenido interno de cada artefacto generado (ZIP, TAR.GZ, RUN, EXE).
        Distingue claramente entre distribuciones completas y ligeras, comprueba la integridad criptográfica
        de componentes anidados y analiza las capas Docker reales.
        Devuelve un mapa con el estado de auditoría verificado por artefacto.
        """
        is_complete = not self.skip_docker and not self.skip_model
        dist_type_label = "COMPLETA (Offline IA y Contenedores)" if is_complete else "LIGERA (Conectividad Dinámica)"
        log(f"Iniciando auditoría profunda de artefactos finales [{dist_type_label}]...", "INFO")

        if not artifacts:
            raise RuntimeError("Auditoría final fallida: No se generó ningún artefacto en dist/.")

        forbidden_names = [".env", "lazyjobfinder.db", "active_cv.json", "secrets.json", "cv_base.md"]
        artifact_audit_status = {}

        # 1. Auditoría profunda en STAGING de componentes base
        staging_images = os.path.join(STAGING_DIR, "images.tar")
        staging_images_hash = None
        if os.path.exists(staging_images):
            staging_images_hash = compute_sha256(staging_images)
            self._audit_docker_layers(staging_images)

        staging_model = os.path.join(STAGING_DIR, "ollama_model.tar.gz")
        staging_model_hash = None
        if os.path.exists(staging_model):
            staging_model_hash = compute_sha256(staging_model)
            self._audit_ollama_model_archive(staging_model)

        # 2. Auditoría sobre cada artefacto de distribución generado
        for art in artifacts:
            filename = os.path.basename(art)
            size_mb = os.path.getsize(art) / (1024 * 1024)
            log(f"  -> Inspeccionando artefacto: {filename} ({size_mb:.1f} MB)...", "INFO")

            member_names = []

            # A. Instalador ejecutable Windows Inno Setup (.exe)
            if filename.endswith(".exe"):
                innoextract_tool = shutil.which("innoextract") or shutil.which("7z")
                if innoextract_tool:
                    import tempfile
                    temp_exe_dir = tempfile.mkdtemp(prefix="lazyjob_audit_exe_")
                    try:
                        log(f"     [EXE] Extrayendo e inspeccionando contenido real de '{filename}' con {innoextract_tool}...", "INFO")
                        if "innoextract" in innoextract_tool.lower():
                            cmd = [innoextract_tool, "-d", temp_exe_dir, art]
                        else:
                            cmd = [innoextract_tool, "x", f"-o{temp_exe_dir}", "-y", art]
                        ret_ex = subprocess.call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        if ret_ex == 0:
                            # 1. Auditoría de seguridad estricta en el contenido extraído
                            self.audit_security(temp_exe_dir)

                            # 2. Validar presencia o ausencia de componentes según tipo de distribución
                            exe_files = []
                            for root_d, _, f_list in os.walk(temp_exe_dir):
                                for f_item in f_list:
                                    exe_files.append(f_item.lower())

                            exe_has_images = "images.tar" in exe_files
                            exe_has_model = "ollama_model.tar.gz" in exe_files
                            exe_has_light = ".light_release" in exe_files

                            expected_has_images = not self.skip_docker and os.path.exists(staging_images)
                            expected_has_model = not self.skip_model and os.path.exists(staging_model)

                            if is_complete:
                                if not exe_has_images:
                                    raise RuntimeError(f"AUDITORÍA EXE FALLIDA: El instalador completo '{filename}' no contiene 'images.tar'.")
                                if not exe_has_model:
                                    raise RuntimeError(f"AUDITORÍA EXE FALLIDA: El instalador completo '{filename}' no contiene 'ollama_model.tar.gz'.")
                                if exe_has_light:
                                    raise RuntimeError(f"AUDITORÍA EXE FALLIDA: El instalador completo '{filename}' contiene inesperadamente '.light_release'.")
                            else:
                                if expected_has_images != exe_has_images:
                                    raise RuntimeError(f"AUDITORÍA EXE FALLIDA: Presencia de 'images.tar' en '{filename}' ({exe_has_images}) no coincide con lo esperado ({expected_has_images}).")
                                if expected_has_model != exe_has_model:
                                    raise RuntimeError(f"AUDITORÍA EXE FALLIDA: Presencia de 'ollama_model.tar.gz' en '{filename}' ({exe_has_model}) no coincide con lo esperado ({expected_has_model}).")
                                if not exe_has_light:
                                    raise RuntimeError(f"AUDITORÍA EXE FALLIDA: El instalador ligero '{filename}' no contiene '.light_release'.")

                            artifact_audit_status[filename] = "verified_deep_extracted"
                            log(f"     [EXE] Inspección interna exhaustiva de '{filename}' superada con éxito ({innoextract_tool}).", "SUCCESS")
                        else:
                            log(
                                f"     [EXE] AVISO: {innoextract_tool} no pudo extraer el instalador .exe. "
                                "El contenido interno NO ha podido ser inspeccionado de forma directa. "
                                "Se acredita únicamente la integridad criptográfica del archivo externo.",
                                "WARN",
                            )
                            artifact_audit_status[filename] = "unverified_contents_hash_only"
                    finally:
                        shutil.rmtree(temp_exe_dir, ignore_errors=True)
                else:
                    log(
                        f"     [EXE] AVISO: innoextract/7z no están disponibles en el host. El contenido interno de '{filename}' "
                        "NO se ha inspeccionado directamente. Se acredita únicamente la integridad criptográfica del archivo externo.",
                        "WARN",
                    )
                    artifact_audit_status[filename] = "unverified_contents_hash_only"

                if is_complete and size_mb < self.min_complete_artifact_size_mb:
                    raise RuntimeError(
                        f"AUDITORÍA FINAL FALLIDA: El instalador '{filename}' pesa solo {size_mb:.1f} MB. "
                        f"Un paquete completo compilado con Inno Setup debe superar {self.min_complete_artifact_size_mb:.1f} MB."
                    )
                continue

            # B. Paquetes comprimidos estándar (ZIP, TAR.GZ, RUN)
            if filename.endswith(".zip"):
                with zipfile.ZipFile(art, "r") as zf:
                    member_names = zf.namelist()
            elif filename.endswith(".tar.gz"):
                with tarfile.open(art, "r:gz") as tf:
                    member_names = tf.getnames()
            elif filename.endswith(".run"):
                with open(art, "rb") as rf:
                    content = rf.read()
                marker = b"__ARCHIVE_STARTS_HERE__\n"
                pos = content.find(marker)
                if pos == -1:
                    raise RuntimeError(f"El instalador .run '{filename}' no contiene el marcador de archivo.")
                tar_bytes = content[pos + len(marker):]
                import io
                with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:gz") as tf:
                    member_names = tf.getnames()

            normalized_names = [os.path.normpath(m).replace("\\", "/") for m in member_names]

            # Comprobación de archivos prohibidos en el árbol del paquete
            for norm_name in normalized_names:
                base_m = os.path.basename(norm_name)
                for f_bad in forbidden_names:
                    if base_m.lower() == f_bad.lower():
                        raise RuntimeError(
                            f"AUDITORÍA FINAL BLOQUEADA: El paquete '{filename}' contiene el archivo confidencial/prohibido: '{norm_name}'."
                        )

            # Comprobación estricta de componentes según tipo de distribución
            has_images = any(m.endswith("images.tar") for m in normalized_names)
            has_model = any(m.endswith("ollama_model.tar.gz") for m in normalized_names)
            has_light = any(m.endswith(".light_release") for m in normalized_names)

            expected_has_images = not self.skip_docker and os.path.exists(staging_images)
            expected_has_model = not self.skip_model and os.path.exists(staging_model)

            if is_complete:
                if not has_images:
                    raise RuntimeError(f"AUDITORÍA FINAL FALLIDA: La distribución completa '{filename}' no contiene 'images.tar'.")
                if not has_model:
                    raise RuntimeError(f"AUDITORÍA FINAL FALLIDA: La distribución completa '{filename}' no contiene 'ollama_model.tar.gz'.")
                if has_light:
                    raise RuntimeError(f"AUDITORÍA FINAL FALLIDA: La distribución completa '{filename}' contiene inesperadamente '.light_release'.")

                if size_mb < self.min_complete_artifact_size_mb:
                    raise RuntimeError(
                        f"AUDITORÍA FINAL FALLIDA: El artefacto completo '{filename}' pesa solo {size_mb:.1f} MB. "
                        f"Un paquete completo con imágenes y modelo debe superar {self.min_complete_artifact_size_mb:.1f} MB."
                    )

                # Exigir de forma obligatoria que los componentes anidados existan y coincidan exactamente
                if not staging_images_hash:
                    raise RuntimeError("Falta el hash de images.tar en staging para validar el paquete.")
                nested_img_hash = self._extract_and_hash_member_from_archive(art, "images.tar")
                if nested_img_hash != staging_images_hash:
                    raise RuntimeError(
                        f"CORRUPCIÓN DETECTADA: 'images.tar' anidado en '{filename}' ({nested_img_hash}) no coincide con staging ({staging_images_hash})."
                    )

                if not staging_model_hash:
                    raise RuntimeError("Falta el hash de ollama_model.tar.gz en staging para validar el paquete.")
                nested_model_hash = self._extract_and_hash_member_from_archive(art, "ollama_model.tar.gz")
                if nested_model_hash != staging_model_hash:
                    raise RuntimeError(
                        f"CORRUPCIÓN DETECTADA: 'ollama_model.tar.gz' anidado en '{filename}' ({nested_model_hash}) no coincide con staging ({staging_model_hash})."
                    )

                artifact_audit_status[filename] = "verified_complete_nested"
            else:
                # Comprobación exhaustiva de coherencia para todas las combinaciones ligeras
                if not has_light:
                    raise RuntimeError(f"AUDITORÍA FALLIDA: El artefacto ligero '{filename}' no incluye el marcador obligatorio '.light_release'.")

                if expected_has_images:
                    if not has_images:
                        raise RuntimeError(f"AUDITORÍA FALLIDA: El paquete '{filename}' debería incluir 'images.tar' pero falta.")
                    if not staging_images_hash:
                        raise RuntimeError("Falta el hash de images.tar en staging para validar el paquete ligero.")
                    nested_img_hash = self._extract_and_hash_member_from_archive(art, "images.tar")
                    if nested_img_hash != staging_images_hash:
                        raise RuntimeError(f"CORRUPCIÓN: 'images.tar' en '{filename}' no coincide con staging.")
                else:
                    if has_images:
                        raise RuntimeError(f"AUDITORÍA FALLIDA: Distribución ligera '{filename}' contiene inesperadamente 'images.tar'.")

                if expected_has_model:
                    if not has_model:
                        raise RuntimeError(f"AUDITORÍA FALLIDA: El paquete '{filename}' debería incluir 'ollama_model.tar.gz' pero falta.")
                    if not staging_model_hash:
                        raise RuntimeError("Falta el hash de ollama_model.tar.gz en staging para validar el paquete ligero.")
                    nested_model_hash = self._extract_and_hash_member_from_archive(art, "ollama_model.tar.gz")
                    if nested_model_hash != staging_model_hash:
                        raise RuntimeError(f"CORRUPCIÓN: 'ollama_model.tar.gz' en '{filename}' no coincide con staging.")
                else:
                    if has_model:
                        raise RuntimeError(f"AUDITORÍA FALLIDA: Distribución ligera '{filename}' contiene inesperadamente 'ollama_model.tar.gz'.")

                artifact_audit_status[filename] = "verified_lightweight"

        log(f"Auditoría final de seguridad e integridad superada con éxito en todos los artefactos ({dist_type_label}).", "SUCCESS")
        return artifact_audit_status

    def emit_release_manifest(self, artifacts: List[str], audit_status_map: Dict[str, str]) -> None:
        """Emite el manifiesto final con verificación criptográfica de ida y vuelta."""
        log("Emitiendo manifiesto de publicación con verificación criptográfica...", "INFO")
        manifest = dict(self.manifest_data)
        manifest["version"] = self.version
        manifest["build_timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        # Derivación exacta de distribution_type según componentes reales
        if self.model_included and not self.skip_docker:
            dist_type = "complete"
        elif not self.skip_docker and not self.model_included:
            dist_type = "lightweight_no_model"
        elif self.skip_docker and self.model_included:
            dist_type = "lightweight_no_docker"
        else:
            dist_type = "lightweight_minimal"

        manifest["distribution_type"] = dist_type
        manifest["components"]["app_image"] = f"lazyjobfinder:{self.version}"
        manifest["components"]["ai_model_prepackaged"] = self.model_included
        manifest["components"]["ai_model_download_fallback"] = not self.model_included

        if "platforms" in manifest:
            for p, p_data in manifest["platforms"].items():
                if "target_file" in p_data:
                    ext = ".exe" if p == "windows" else ".run"
                    p_data["target_file"] = f"lazyJobFinder-{self.version}-{p}-x64{ext}"
                if "portable_archive" in p_data:
                    p_data["portable_archive"] = f"lazyJobFinder-{self.version}-{p}-x64.zip"
                if "archive" in p_data:
                    p_data["archive"] = f"lazyJobFinder-{self.version}-{p}-x64.tar.gz"

        manifest["artifacts"] = []
        sums_lines = []
        for artifact in artifacts:
            filename = os.path.basename(artifact)
            size = os.path.getsize(artifact)
            sha = compute_sha256(artifact)
            verified_state = audit_status_map.get(filename, "verified")

            manifest["artifacts"].append({
                "filename": filename,
                "size_bytes": size,
                "size_mb": round(size / (1024 * 1024), 2),
                "sha256": sha,
                "audit_status": verified_state,
            })
            sums_lines.append(f"{sha}  {filename}")

        manifest_path = os.path.join(DIST_DIR, "release-manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

        sums_path = os.path.join(DIST_DIR, "SHA256SUMS.txt")
        with open(sums_path, "w", encoding="utf-8") as f:
            f.write("\n".join(sums_lines) + "\n")

        # Verificación de ida y vuelta estricta: volver a leer SHA256SUMS.txt y contrastar con disco
        log("Realizando verificación de ida y vuelta sobre SHA256SUMS.txt...", "INFO")
        with open(sums_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(maxsplit=1)
                if len(parts) == 2:
                    expected_hash, target_file = parts[0], parts[1]
                    real_file_path = os.path.join(DIST_DIR, target_file)
                    if not os.path.exists(real_file_path):
                        raise RuntimeError(f"Verificación de sumas fallida: '{target_file}' no existe en dist/.")
                    computed = compute_sha256(real_file_path)
                    if computed != expected_hash:
                        raise RuntimeError(
                            f"Verificación de sumas fallida: el hash de '{target_file}' ({computed}) no coincide con el registrado ({expected_hash})."
                        )

        log(f"Manifiesto y sumas de comprobación verificados al 100% (ida y vuelta).", "SUCCESS")

        log("Auditoría final de seguridad e integridad superada con éxito en todos los artefactos.", "SUCCESS")

    def run(self, platforms_target: str = "all") -> None:
        start_time = time.time()
        print("\n" + "=" * 70)
        print(f"       CONSTRUCCIÓN DE DISTRIBUCIÓN lazyJobFinder v{self.version}")
        print("=" * 70 + "\n")

        # 1. Auditoría inicial de plantillas
        self.audit_security(CONFIG_TEMPLATES_DIR)

        # 2. Verificación del frontend estático
        self.verify_frontend()

        # 3. Preparación del directorio staging y auditoría de staging
        self.prepare_staging()

        # 4. Construcción y empaquetado de imágenes Docker (en contexto aislado)
        self.build_docker_images()

        # 5. Exportación del modelo Ollama (independiente de --skip-docker)
        if not self.skip_model:
            self.export_ollama_model()
        else:
            log("Distribución configurada como LIGERA (--skip-model): se omitirá el modelo de IA en el paquete.", "WARN")
            self.model_included = False

        # 6. Generación de artefactos según plataforma
        artifacts = []
        build_windows = platforms_target in ("all", "windows")
        build_linux = platforms_target in ("all", "linux")

        if build_windows:
            artifacts.extend(self.build_windows_distribution())

        if build_linux:
            artifacts.extend(self.build_linux_distribution())

        # 6. Auditoría final sobre artefactos empaquetados
        audit_status_map = self.audit_final_artifacts(artifacts)

        # 7. Manifiesto e integridad
        self.emit_release_manifest(artifacts, audit_status_map)


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
        help="Omitir exportación pesada del modelo de Ollama en archivo tar",
    )
    parser.add_argument(
        "--build-frontend",
        action="store_true",
        help="Compilar 'npm run build' si falta web/out",
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
        build_frontend=args.build_frontend,
    )
    builder.run(platforms_target=args.platform)


if __name__ == "__main__":
    main()
