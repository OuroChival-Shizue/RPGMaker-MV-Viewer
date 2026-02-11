from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from viewer.java_mv_decrypter import find_java_decrypter_jar, run_java_decrypt


class JavaMvDecrypterTest(unittest.TestCase):
    def test_find_java_decrypter_jar_from_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            jar = Path(tmp) / "custom.jar"
            jar.write_bytes(b"jar")
            with mock.patch.dict(os.environ, {"RPGMV_JAVA_DECRYPTER_JAR": str(jar)}):
                found = find_java_decrypter_jar(tmp)
            self.assertEqual(found, jar.resolve())

    def test_find_java_decrypter_jar_from_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "Java-RPG-Maker-MV-Decrypter-master" / "x" / "target"
            target.mkdir(parents=True)
            jar = target / "RPG Maker MV Decrypter 0.4.2.jar"
            jar.write_bytes(b"jar")
            found = find_java_decrypter_jar(root)
            self.assertEqual(found, jar.resolve())

    def test_run_java_decrypt_no_jar(self):
        ok, message = run_java_decrypt("/tmp/a", "/tmp/b", None)
        self.assertFalse(ok)
        self.assertIn("缺少 Java Decrypter", message)

    def test_run_java_decrypt_invokes_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            jar = root / "tool.jar"
            jar.write_bytes(b"jar")
            out = root / "out"
            with mock.patch("viewer.java_mv_decrypter.subprocess.run") as run_mock:
                run_mock.return_value = mock.Mock(returncode=0, stdout="Done", stderr="")
                ok, _ = run_java_decrypt(root, out, jar)
            self.assertTrue(ok)
            self.assertTrue(out.exists())
            called = run_mock.call_args[0][0]
            self.assertEqual(called[:4], ["java", "-jar", str(jar.resolve()), "decrypt"])


if __name__ == "__main__":
    unittest.main()

