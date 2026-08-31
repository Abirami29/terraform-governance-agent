"""
scripts/test_duplicate_check_e2e.py
One real end-to-end call against the pair we already know the answer
to — s3-bucket-standard and s3-bucket-legacy are a deliberately
planted near-duplicate pair. Not a pytest test — read the printed
output by hand first.

NOTE: this repo's modules have no README.md (unlike module-wise),
so there's no real prose "description" to pass in. Using the raw
main.tf content as a stand-in description here — good enough to
test whether the check functions, but if you want a more realistic
signal later, consider adding short READMEs to the sample modules.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.llm_checks.duplicate_check import check_duplicate_capability

RESOURCE_TYPE_RE = re.compile(r'resource\s+"([a-zA-Z0-9_]+)"')


def load_module(name: str):
    path = Path(f"data/sample-repos/infra-modules/modules/{name}/main.tf")
    text = path.read_text()
    resource_types = RESOURCE_TYPE_RE.findall(text)
    return text, resource_types


desc_a, resources_a = load_module("s3-bucket-standard")
desc_b, resources_b = load_module("s3-bucket-legacy")

finding = check_duplicate_capability(
    "s3-bucket-standard", "s3-bucket-legacy",
    desc_a, desc_b, resources_a, resources_b,
)

print(finding)