"""
scripts/test_security_check_e2e.py
One real end-to-end call against the module we already know the
answer for (security-group-web has the planted open-SSH-ingress
issue). Not a pytest test — read the printed output by hand first.
"""
import sys
from pathlib import Path

# scripts/ isn't run through pytest, so pytest.ini's pythonpath=.
# setting doesn't apply here — add the repo root manually.
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.llm_checks.security_check import check_module_security

module_path = Path("data/sample-repos/infra-modules/modules/security-group-web/main.tf")
resource_text = module_path.read_text()

findings = check_module_security("security-group-web", resource_text)

print(f"Got {len(findings)} finding(s):\n")
for f in findings:
    print(f)