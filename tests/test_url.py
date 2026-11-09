"""Run with python3 -m unittest discover -s tests -v (requires Ansible)."""

import contextlib
import http.server
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest

import yaml


ROLE = Path(__file__).resolve().parents[1]
RPM_CONTENT = b"test RPM download payload\n"


@contextlib.contextmanager
def http_artifact():
    requests = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_HEAD(self):
            requests.append("HEAD")
            self.send_response(200)
            self.send_header("Content-Length", str(len(RPM_CONTENT)))
            self.end_headers()

        def do_GET(self):
            requests.append("GET")
            self.send_response(200)
            self.send_header("Content-Length", str(len(RPM_CONTENT)))
            self.end_headers()
            self.wfile.write(RPM_CONTENT)

        def log_message(self, *_args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/package.rpm", requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@unittest.skipUnless(shutil.which("ansible-playbook"), "ansible-playbook is required")
class URLPackageTests(unittest.TestCase):
    def run_playbook(self, root, play, check=False):
        playbook = root / "playbook.json"
        playbook.write_text(json.dumps([play]))
        command = ["ansible-playbook", "-i", "localhost,", str(playbook)]
        if check:
            command.append("--check")
        env = dict(os.environ, ANSIBLE_NOCOLOR="1", ANSIBLE_NOCOWS="1")
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=60, env=env
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    def test_check_mode_with_missing_and_existing_staging_directory(self):
        with http_artifact() as (url, requests):
            for existing in (False, True):
                with self.subTest(existing=existing), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    staging = root / "staging"
                    artifact = staging / "package.rpm"
                    if existing:
                        staging.mkdir()
                        artifact.write_bytes(b"existing RPM")
                    output = self.run_playbook(root, {
                        "hosts": "localhost",
                        "connection": "local",
                        "gather_facts": False,
                        "vars": {
                            "ansible_facts": {"os_family": "RedHat"},
                            "packages": [{
                                "source": "url", "url": url,
                                "tmp_dir": str(staging),
                            }],
                        },
                        "roles": [{"role": str(ROLE)}],
                    }, check=True)
                    self.assertIn("Check mode skips RPM downloads", output)
                    self.assertEqual(requests, [])
                    if existing:
                        self.assertEqual(artifact.read_bytes(), b"existing RPM")
                    else:
                        self.assertFalse(staging.exists())

    def test_normal_mode_downloads_over_http(self):
        # Exercise the real download tasks without installing a package on the controller.
        tasks = yaml.safe_load((ROLE / "tasks/url.yml").read_text())
        install = next(i for i, task in enumerate(tasks)
                       if "ansible.builtin.package" in task)
        defaults = yaml.safe_load((ROLE / "defaults/main.yml").read_text())
        settings = {key[len("package_"):]: value for key, value in defaults.items()
                    if key.startswith("package_")}
        with tempfile.TemporaryDirectory() as tmp, http_artifact() as (url, requests):
            root = Path(tmp)
            staging = root / "staging"
            settings.update(url=url, tmp_dir=str(staging))
            self.run_playbook(root, {
                "hosts": "localhost",
                "connection": "local",
                "gather_facts": False,
                "vars": {"_package": settings},
                "tasks": tasks[:install],
            })
            self.assertIn("GET", requests)
            self.assertEqual((staging / "package.rpm").read_bytes(), RPM_CONTENT)


if __name__ == "__main__":
    unittest.main()
