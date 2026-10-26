import os
import sys
import tempfile
import tarfile
import zipfile
import json
import hashlib
import unittest
import io
from unittest.mock import patch, MagicMock

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT_DIR, "packaging"))

try:
    import build_release
    from build_release import ReleaseBuilder, compute_sha256
except ImportError:
    build_release = None
    from typing import Any
    ReleaseBuilder = Any
    compute_sha256 = None

def make_blob(content: bytes) -> tuple[str, bytes]:
    digest = hashlib.sha256(content).hexdigest()
    return digest, content

class PackagingEdgeCasesTest(unittest.TestCase):
    def setUp(self):
        if build_release is None:
            self.skipTest("Módulo packaging/build_release no disponible en este entorno")
        self.temp_dir = tempfile.mkdtemp()
        self.fast_weight_size = 256 # Fast lightweight size for unit tests
        self.weight_content = b"WeightBlobDataA1234567890" * 10
        self.layer_d, _ = make_blob(self.weight_content)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_fast_model_tar(self, tar_path, include_3b=True, include_latest=False, 
                               latest_different=False):
        content_cfg = b'{"architecture": "qwen2"}'
        cfg_d, _ = make_blob(content_cfg)

        manifest_3b_data = {
            "schemaVersion": 2,
            "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
            "config": {"digest": f"sha256:{cfg_d}"},
            "layers": [{"digest": f"sha256:{self.layer_d}"}]
        }

        if latest_different:
            diff_d, _ = make_blob(b'{"different": true}')
            manifest_latest_data = {
                "schemaVersion": 2,
                "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
                "config": {"digest": f"sha256:{diff_d}"},
                "layers": [{"digest": f"sha256:{self.layer_d}"}]
            }
        else:
            manifest_latest_data = dict(manifest_3b_data)

        with tarfile.open(tar_path, "w:gz") as tf:
            if include_3b:
                data_b = json.dumps(manifest_3b_data).encode("utf-8")
                ti = tarfile.TarInfo("manifests/registry.ollama.ai/library/qwen2.5/3b-instruct")
                ti.size = len(data_b)
                tf.addfile(ti, io.BytesIO(data_b))

            if include_latest:
                data_b = json.dumps(manifest_latest_data).encode("utf-8")
                ti = tarfile.TarInfo("manifests/registry.ollama.ai/library/qwen2.5/latest")
                ti.size = len(data_b)
                tf.addfile(ti, io.BytesIO(data_b))

            # Add cfg blob
            ti_cfg = tarfile.TarInfo(f"blobs/sha256-{cfg_d}")
            ti_cfg.size = len(content_cfg)
            tf.addfile(ti_cfg, io.BytesIO(content_cfg))

            # Add weight blob (matched by min_weight_blob_size_bytes in unit test)
            ti_lyr = tarfile.TarInfo(f"blobs/sha256-{self.layer_d}")
            ti_lyr.size = len(self.weight_content)
            tf.addfile(ti_lyr, io.BytesIO(self.weight_content))

        return cfg_d, self.layer_d

    def _configure_builder_for_unit_tests(self, builder: ReleaseBuilder) -> None:
        builder.min_weight_blob_size_bytes = len(self.weight_content)
        builder.min_complete_artifact_size_mb = 0.0

    def test_model_audit_only_3b_instruct(self):
        """Test that an archive with only 3b-instruct passes and sets _staging_model_digests."""
        tar_path = os.path.join(self.temp_dir, "model_3b.tar.gz")
        cfg_d, layer_d = self._create_fast_model_tar(tar_path, include_3b=True, include_latest=False)

        builder = ReleaseBuilder()
        self._configure_builder_for_unit_tests(builder)
        builder._audit_ollama_model_archive(tar_path)
        self.assertIsNotNone(builder._staging_model_digests)
        self.assertEqual(builder._staging_model_digests, [cfg_d, layer_d])

    def test_model_audit_both_match(self):
        """Test that an archive with both 3b-instruct and latest matching passes."""
        tar_path = os.path.join(self.temp_dir, "model_both.tar.gz")
        cfg_d, layer_d = self._create_fast_model_tar(tar_path, include_3b=True, include_latest=True, latest_different=False)

        builder = ReleaseBuilder()
        self._configure_builder_for_unit_tests(builder)
        builder._audit_ollama_model_archive(tar_path)
        self.assertIsNotNone(builder._staging_model_digests)
        self.assertEqual(builder._staging_model_digests, [cfg_d, layer_d])

    def test_model_audit_both_conflict_rejected(self):
        """Test that an archive where 3b-instruct and latest differ is strictly rejected."""
        tar_path = os.path.join(self.temp_dir, "model_conflict.tar.gz")
        self._create_fast_model_tar(tar_path, include_3b=True, include_latest=True, latest_different=True)

        builder = ReleaseBuilder()
        self._configure_builder_for_unit_tests(builder)
        with self.assertRaises(RuntimeError) as cm:
            builder._audit_ollama_model_archive(tar_path)
        self.assertIn("Conflicto entre manifiestos", str(cm.exception))

    def test_model_audit_only_latest_without_reference_rejected(self):
        """Test that an archive containing ONLY latest is rejected if there is no prior independent reference."""
        tar_path = os.path.join(self.temp_dir, "model_only_latest.tar.gz")
        self._create_fast_model_tar(tar_path, include_3b=False, include_latest=True)

        builder = ReleaseBuilder()
        self._configure_builder_for_unit_tests(builder)
        with self.assertRaises(RuntimeError) as cm:
            builder._audit_ollama_model_archive(tar_path)
        self.assertIn("No se puede aceptar la etiqueta 'latest' sin una referencia independiente previa", str(cm.exception))

    def test_model_audit_only_latest_with_matching_reference_accepted(self):
        """Test that an archive with ONLY latest is accepted if its digests match _staging_model_digests."""
        tar_path = os.path.join(self.temp_dir, "model_only_latest_ref.tar.gz")
        cfg_d, layer_d = self._create_fast_model_tar(tar_path, include_3b=False, include_latest=True)

        builder = ReleaseBuilder()
        self._configure_builder_for_unit_tests(builder)
        builder._staging_model_digests = [cfg_d, layer_d]
        builder._audit_ollama_model_archive(tar_path)
        self.assertEqual(builder._staging_model_digests, [cfg_d, layer_d])

    def test_model_audit_only_latest_with_mismatched_reference_rejected(self):
        """Test that an archive with ONLY latest is rejected if digests do not match _staging_model_digests."""
        tar_path = os.path.join(self.temp_dir, "model_only_latest_mismatch.tar.gz")
        cfg_d, layer_d = self._create_fast_model_tar(tar_path, include_3b=False, include_latest=True)

        builder = ReleaseBuilder()
        self._configure_builder_for_unit_tests(builder)
        builder._staging_model_digests = ["deadbeef" * 8, layer_d]
        with self.assertRaises(RuntimeError) as cm:
            builder._audit_ollama_model_archive(tar_path)
        self.assertIn("no coincide con los digests de referencia", str(cm.exception))

    def test_docker_layers_audit_strict(self):
        """Test strict manifest.json requirement and rejection of empty/missing layers."""
        builder = ReleaseBuilder()
        
        # Test 1: No manifest.json
        no_manifest_tar = os.path.join(self.temp_dir, "no_manifest.tar")
        with tarfile.open(no_manifest_tar, "w") as tf:
            ti = tarfile.TarInfo("dummy.txt")
            ti.size = 4
            tf.addfile(ti, io.BytesIO(b"test"))
        
        with self.assertRaises(RuntimeError) as cm:
            builder._audit_docker_layers(no_manifest_tar)
        self.assertIn("no contiene el archivo canónico 'manifest.json'", str(cm.exception))

        # Test 2: manifest.json with empty Layers
        empty_layers_tar = os.path.join(self.temp_dir, "empty_layers.tar")
        with tarfile.open(empty_layers_tar, "w") as tf:
            m_content = json.dumps([{"Layers": []}]).encode("utf-8")
            ti = tarfile.TarInfo("manifest.json")
            ti.size = len(m_content)
            tf.addfile(ti, io.BytesIO(m_content))

        with self.assertRaises(RuntimeError) as cm:
            builder._audit_docker_layers(empty_layers_tar)
        self.assertIn("no define ninguna capa obligatoria", str(cm.exception))

    def test_distribution_modes_emit_real_manifest(self):
        """
        Invokes emit_release_manifest() directly and validates the actual generated release-manifest.json
        for all 4 combinations:
        1. Sin opciones --skip-* -> 'complete'
        2. --skip-model -> 'lightweight_no_model'
        3. --skip-docker -> 'lightweight_no_docker'
        4. --skip-docker --skip-model -> 'lightweight_minimal'
        """
        modes = [
            (True, False, False, "complete", True),
            (False, False, True, "lightweight_no_model", False),
            (True, True, False, "lightweight_no_docker", True),
            (False, True, True, "lightweight_minimal", False),
        ]

        old_dist = build_release.DIST_DIR
        test_dist = os.path.join(self.temp_dir, "test_dist_manifests")
        os.makedirs(test_dist, exist_ok=True)
        build_release.DIST_DIR = test_dist

        try:
            for model_inc, skip_doc, skip_mod, expected_type, expected_prepack in modes:
                builder = ReleaseBuilder(skip_docker=skip_doc, skip_model=skip_mod)
                builder.model_included = model_inc

                # Create dummy valid artifact in test_dist
                art_name = f"lazyJobFinder-1.0.0-windows-x64-{expected_type}.zip"
                art_path = os.path.join(test_dist, art_name)
                with open(art_path, "wb") as f:
                    f.write(b"PK\x05\x06" + b"\x00" * 18)

                audit_map = {art_name: "verified_test"}
                # Invoke the REAL method that writes release-manifest.json
                builder.emit_release_manifest([art_path], audit_map)

                manifest_file = os.path.join(test_dist, "release-manifest.json")
                self.assertTrue(os.path.exists(manifest_file), "release-manifest.json must be created")

                with open(manifest_file, "r", encoding="utf-8") as f:
                    real_manifest = json.load(f)

                self.assertEqual(
                    real_manifest.get("distribution_type"),
                    expected_type,
                    f"Expected distribution_type '{expected_type}' in real manifest, got '{real_manifest.get('distribution_type')}'"
                )
                self.assertEqual(
                    real_manifest["components"].get("ai_model_prepackaged"),
                    expected_prepack,
                    f"Expected ai_model_prepackaged={expected_prepack} for mode '{expected_type}'"
                )
        finally:
            build_release.DIST_DIR = old_dist

    def test_export_ollama_model_failure_is_blocking(self):
        """
        Test that failure to capture the canonical reference manifest from the container
        strictly aborts export_ollama_model with RuntimeError.
        """
        builder = ReleaseBuilder()
        with patch("subprocess.run") as mock_run:
            def mock_sub_run(cmd, *args, **kwargs):
                cmd_str = " ".join(cmd) if isinstance(cmd, list) else str(cmd)
                if "cat" in cmd_str and "manifests" in cmd_str:
                    return MagicMock(returncode=1, stderr="No such file\n", stdout="")
                if "ollama" in cmd_str and "list" in cmd_str:
                    return MagicMock(returncode=0, stdout="qwen2.5:3b-instruct\n")
                return MagicMock(returncode=0, stderr="", stdout="")

            mock_run.side_effect = mock_sub_run

            with self.assertRaises(RuntimeError) as cm:
                builder.export_ollama_model()
            self.assertIn("No se pudo leer el manifiesto canónico", str(cm.exception))

    def test_skip_docker_preserves_model_export(self):
        """
        Test that --skip-docker does NOT omit export_ollama_model when skip_model is False.
        """
        builder = ReleaseBuilder(skip_docker=True, skip_model=False)
        with patch.object(builder, "build_docker_images") as mock_build_img, \
             patch.object(builder, "export_ollama_model") as mock_export_mod, \
             patch.object(builder, "audit_security"), \
             patch.object(builder, "verify_frontend"), \
             patch.object(builder, "prepare_staging"), \
             patch.object(builder, "build_windows_distribution", return_value=[]), \
             patch.object(builder, "build_linux_distribution", return_value=[]), \
             patch.object(builder, "audit_final_artifacts", return_value={}), \
             patch.object(builder, "emit_release_manifest"):

            builder.run()
            mock_build_img.assert_called_once()
            mock_export_mod.assert_called_once()

    def test_artifacts_audit_lightweight_requires_marker(self):
        """Test that a lightweight distribution artifact missing .light_release is rejected."""
        builder = ReleaseBuilder(skip_docker=True, skip_model=True)
        art_zip = os.path.join(self.temp_dir, "lazyJobFinder-1.0.0-windows-x64.zip")
        with zipfile.ZipFile(art_zip, "w") as zf:
            zf.writestr("docker-compose.yml", "services: {}")
            zf.writestr("launch.bat", "echo hi")

        old_staging = build_release.STAGING_DIR
        test_staging = os.path.join(self.temp_dir, "mock_staging")
        os.makedirs(test_staging, exist_ok=True)
        build_release.STAGING_DIR = test_staging
        try:
            with self.assertRaises(RuntimeError) as cm:
                builder.audit_final_artifacts([art_zip])
            self.assertIn("no incluye el marcador obligatorio '.light_release'", str(cm.exception))
        finally:
            build_release.STAGING_DIR = old_staging

    def test_artifacts_audit_complete_rejects_light_marker(self):
        """Test that a complete distribution artifact containing .light_release is rejected."""
        builder = ReleaseBuilder(skip_docker=False, skip_model=False)
        builder.model_included = True
        self._configure_builder_for_unit_tests(builder)

        old_staging = build_release.STAGING_DIR
        test_staging = os.path.join(self.temp_dir, "mock_staging_comp")
        os.makedirs(test_staging, exist_ok=True)
        build_release.STAGING_DIR = test_staging

        try:
            staging_img = os.path.join(test_staging, "images.tar")
            layer_buf = io.BytesIO()
            with tarfile.open(fileobj=layer_buf, mode="w") as ltf:
                t_info = tarfile.TarInfo("file.txt")
                t_info.size = 7
                ltf.addfile(t_info, io.BytesIO(b"content"))
            m_layer_data = layer_buf.getvalue()

            with tarfile.open(staging_img, "w") as tf:
                ti_m = tarfile.TarInfo("layer1.tar")
                ti_m.size = len(m_layer_data)
                tf.addfile(ti_m, io.BytesIO(m_layer_data))
                m_json = json.dumps([{"Layers": ["layer1.tar"]}]).encode("utf-8")
                ti_j = tarfile.TarInfo("manifest.json")
                ti_j.size = len(m_json)
                tf.addfile(ti_j, io.BytesIO(m_json))

            staging_mod = os.path.join(test_staging, "ollama_model.tar.gz")
            self._create_fast_model_tar(staging_mod, include_3b=True, include_latest=False)

            art_zip = os.path.join(self.temp_dir, "lazyJobFinder-1.0.0-windows-x64.zip")
            with zipfile.ZipFile(art_zip, "w") as zf:
                zf.write(staging_img, "images.tar")
                zf.write(staging_mod, "ollama_model.tar.gz")
                zf.writestr(".light_release", "light")

            with self.assertRaises(RuntimeError) as cm:
                builder.audit_final_artifacts([art_zip])
            self.assertIn("contiene inesperadamente '.light_release'", str(cm.exception))
        finally:
            build_release.STAGING_DIR = old_staging

if __name__ == "__main__":
    unittest.main()
