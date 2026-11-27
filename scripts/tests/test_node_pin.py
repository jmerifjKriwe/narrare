"""The image's web stage builds on the Node major ``.nvmrc`` pins.

The runner's Node version comes from ``.nvmrc``; the release bundle's comes from
the ``node:`` base image in the ``Dockerfile``. The two move together or they
disagree, so this test reads both and requires every ``FROM node:`` line to
carry the pinned major — including a second Node stage added later.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NVM_RC = ROOT / ".nvmrc"
DOCKERFILE = ROOT / "Dockerfile"


class NodePinTests(unittest.TestCase):
    def test_every_dockerfile_node_stage_uses_the_nvmrc_major(self):
        pin = NVM_RC.read_text(encoding="utf-8").strip()
        pinned_major = pin.split(".", 1)[0]
        dockerfile = DOCKERFILE.read_text(encoding="utf-8")
        stages = re.findall(r"^FROM\s+node:(\S+)", dockerfile, re.MULTILINE)
        self.assertTrue(stages, f"{DOCKERFILE.name} carries no FROM node: stage")
        for image in stages:
            tag = image.split("@", 1)[0]
            major = tag.split("-", 1)[0]
            self.assertEqual(
                major,
                pinned_major,
                f"{DOCKERFILE.name} builds on node:{tag}, but {NVM_RC.name} pins "
                f"major {pinned_major}: this stage's Node major must be the major "
                f"{NVM_RC.name} names. A Dependabot pull request that crosses the "
                "major stays red until the pin moves with it.",
            )


if __name__ == "__main__":
    unittest.main()
