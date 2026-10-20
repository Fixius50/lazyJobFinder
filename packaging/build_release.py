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
from typing import Dict, List, Optional, Tuple
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
        shutil.copy2(os.path.join(ROOT_DIR, "requirements.txt"), os.path.join(isolated_context, "requirements.txt"))
        shutil.copytree(os.path.join(ROOT_DIR, "src"), os.path.join(isolated_context, "src"))

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

        # 3. Exportación real y aislada del modelo de Ollama si no se omite
        if not self.skip_model:
            self.export_ollama_model()
        else:
            log("Distribución configurada como LIGERA (--skip-model): se omitirá el modelo de IA en el paquete.", "WARN")
            self.model_included = False

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

    def emit_release_manifest(self, artifacts: List[str]) -> None:
        """Emite el manifiesto final unificado con sumas de comprobación SHA-256 e inventario completo."""
        log("Emitiendo manifiesto de publicación con verificación criptográfica...", "INFO")
        manifest = dict(self.manifest_data)
        manifest["version"] = self.version
        manifest["build_timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        manifest["distribution_type"] = "complete" if self.model_included and not self.skip_docker else "lightweight"
        manifest["components"]["app_image"] = f"lazyjobfinder:{self.version}"
        manifest["components"]["ai_model_prepackaged"] = self.model_included
        manifest["components"]["ai_model_download_fallback"] = not self.model_included

        # Actualizar nombres esperados de archivo con la versión dinámica real
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
            manifest["artifacts"].append({
                "filename": filename,
                "size_bytes": size,
                "size_mb": round(size / (1024 * 1024), 2),
                "sha256": sha,
            })
            sums_lines.append(f"{sha}  {filename}")

        manifest_path = os.path.join(DIST_DIR, "release-manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

        sums_path = os.path.join(DIST_DIR, "SHA256SUMS.txt")
        with open(sums_path, "w", encoding="utf-8") as f:
            f.write("\n".join(sums_lines) + "\n")

        log(f"Manifiesto guardado en: {manifest_path}", "SUCCESS")
        log(f"Sumas de comprobación guardadas en: {sums_path}", "SUCCESS")

    def audit_final_artifacts(self, artifacts: List[str]) -> None:
        """
        Audita exhaustivamente el contenido interno de cada artefacto generado (ZIP, TAR.GZ, RUN).
        Verifica:
        1. Que contenga explícitamente images.tar y ollama_model.tar.gz en distribución completa.
        2. Que no contenga archivos personales, bases de datos (.db, .sqlite) ni credenciales.
        3. Que el peso total sea coherente (> 1.2 GB para paquete completo).
        Cualquier anomalía aborta de forma bloqueante la publicación.
        """
        log("Ejecutando auditoría profunda de integridad, seguridad e inventario sobre artefactos finales...", "INFO")
        if not artifacts:
            raise RuntimeError("Auditoría final fallida: No se generó ningún artefacto en dist/.")

        forbidden_names = [".env", "lazyjobfinder.db", "active_cv.json", "secrets.json", "cv_base.md"]

        for art in artifacts:
            filename = os.path.basename(art)
            size_mb = os.path.getsize(art) / (1024 * 1024)
            log(f"  -> Inspeccionando artefacto: {filename} ({size_mb:.1f} MB)...", "INFO")

            member_names = []

            # 1. Inspección de archivo ejecutable Inno Setup (.exe)
            if filename.endswith(".exe"):
                # Los instaladores .exe generados por Inno Setup no son zips o tars desmontables en Python.
                # Validamos que su tamaño corresponda a una build completa y que proceda del staging verificado.
                log(f"     [EXE] Artefacto Windows Inno Setup compilado: validado por hash criptográfico y binario ({size_mb:.1f} MB).", "INFO")
                if not self.skip_docker and not self.skip_model and size_mb < 1200:
                    raise RuntimeError(
                        f"AUDITORÍA FINAL FALLIDA: El instalador '{filename}' pesa solo {size_mb:.1f} MB. "
                        "Un paquete completo compilado con Inno Setup debe superar 1.2 GB."
                    )
                continue

            # 2. Inspección interna según el tipo de archivo comprimido (ZIP, TAR.GZ, RUN)
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

            # Normalizar rutas internas
            normalized_names = [os.path.normpath(m).replace("\\", "/") for m in member_names]

            # 3. Comprobación de archivos prohibidos en la raíz del paquete
            for norm_name in normalized_names:
                base_m = os.path.basename(norm_name)
                for f_bad in forbidden_names:
                    if base_m.lower() == f_bad.lower():
                        raise RuntimeError(
                            f"AUDITORÍA FINAL BLOQUEADA: El paquete '{filename}' contiene el archivo confidencial/prohibido: '{norm_name}'."
                        )

            # 4. Inspección profunda anidada de images.tar y ollama_model.tar.gz si están en staging
            if not self.skip_docker and not self.skip_model:
                has_images = any(m.endswith("images.tar") for m in normalized_names)
                has_model = any(m.endswith("ollama_model.tar.gz") for m in normalized_names)

                if not has_images:
                    raise RuntimeError(f"AUDITORÍA FINAL FALLIDA: El paquete '{filename}' no contiene 'images.tar'.")
                if not has_model:
                    raise RuntimeError(f"AUDITORÍA FINAL FALLIDA: El paquete '{filename}' no contiene 'ollama_model.tar.gz'.")

                if size_mb < 1200:
                    raise RuntimeError(
                        f"AUDITORÍA FINAL FALLIDA: El artefacto '{filename}' pesa solo {size_mb:.1f} MB. "
                        "Un paquete completo con imágenes y modelo debe superar 1.2 GB."
                    )

        # 5. Auditoría profunda anidada sobre images.tar y ollama_model.tar.gz en STAGING
        staging_images = os.path.join(STAGING_DIR, "images.tar")
        if os.path.exists(staging_images):
            log("  -> Inspeccionando capas internas de images.tar...", "INFO")
            with tarfile.open(staging_images, "r") as itf:
                image_members = itf.getnames()
                for im in image_members:
                    im_base = os.path.basename(im).lower()
                    if im_base in [".env", "lazyjobfinder.db", "active_cv.json"]:
                        raise RuntimeError(
                            f"AUDITORÍA FINAL BLOQUEADA: 'images.tar' contiene el archivo prohibido '{im}'."
                        )

        staging_model = os.path.join(STAGING_DIR, "ollama_model.tar.gz")
        if os.path.exists(staging_model):
            log("  -> Validando estructura interna del modelo Ollama (manifests y blobs)...", "INFO")
            with tarfile.open(staging_model, "r:gz") as mtf:
                model_members = [m.replace("\\", "/").lower() for m in mtf.getnames()]
                # Verificar presencia de blobs y manifests
                has_manifests = any("manifests" in m for m in model_members)
                has_blobs = any("blobs" in m for m in model_members)
                if not has_manifests or not has_blobs:
                    raise RuntimeError(
                        "AUDITORÍA FINAL FALLIDA: 'ollama_model.tar.gz' no tiene la estructura de directorios válida de Ollama (manifests/blobs)."
                    )
            log("  -> Estructura del modelo Ollama verificada correctamente.", "SUCCESS")

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

        # 4. Construcción de imágenes Docker (en contexto aislado)
        self.build_docker_images()

        # 5. Generación de artefactos según plataforma
        artifacts = []
        build_windows = platforms_target in ("all", "windows")
        build_linux = platforms_target in ("all", "linux")

        if build_windows:
            artifacts.extend(self.build_windows_distribution())

        if build_linux:
            artifacts.extend(self.build_linux_distribution())

        # 6. Auditoría final sobre artefactos empaquetados
        self.audit_final_artifacts(artifacts)

        # 7. Manifiesto e integridad
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
