"""Exercise the actual selection shell block with owned, credential-free fixtures."""
import os
from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest


class SelectionBootstrap(unittest.TestCase):
    def run_selection(self, helper):
        root = Path(__file__).resolve().parents[2]
        workflow = (root / ".github/workflows/pr.yml").read_text()
        step = workflow.split("      - name: Select the tests\n", 1)[1]
        block = step.split("      - name: Upload the selection\n", 1)[0]
        script = textwrap.dedent(block.split("        run: |\n", 1)[1])
        with tempfile.TemporaryDirectory(prefix="selection-bootstrap-") as directory:
            owned = Path(directory)
            output = owned / "output"
            if helper:
                executable = owned / "base-tooling/scripts/ci/test-impact-select.sh"
                executable.parent.mkdir(parents=True)
                executable.write_text(
                    '#!/bin/sh\nset -eu\n'
                    'test "$1" = --repo\n'
                    'test "$2" = "$GITHUB_WORKSPACE"\n'
                    'printf "selection=narrowed\\nportable=narrowed\\n" >> "$GITHUB_OUTPUT"\n'
                )
                executable.chmod(0o700)
            # Deliberately poison the PR's helper. It must never be used when
            # the trusted base lacks its own selector.
            untrusted = owned / "workspace/scripts/ci/test-impact-select.sh"
            untrusted.parent.mkdir(parents=True)
            untrusted.write_text("#!/bin/sh\nexit 99\n")
            untrusted.chmod(0o700)
            env = {
                "PATH": os.defpath,
                "RUNNER_TEMP": str(owned),
                "GITHUB_WORKSPACE": str(owned / "workspace"),
                "GITHUB_OUTPUT": str(output),
            }
            result = subprocess.run(
                ["/bin/bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", script],
                env=env, capture_output=True, text=True, timeout=5,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            return output.read_text()

    def test_missing_trusted_selector_runs_all_despite_poisoned_pr_helper(self):
        self.assertEqual(self.run_selection(False), "selection=all\nportable=all\n")

    def test_existing_trusted_selector_keeps_its_narrowed_answer(self):
        self.assertEqual(self.run_selection(True), "selection=narrowed\nportable=narrowed\n")


if __name__ == "__main__":
    unittest.main()
