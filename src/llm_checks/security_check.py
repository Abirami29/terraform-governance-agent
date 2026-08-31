"""
LLM-judgment security check — real implementation.
"""
from dataclasses import dataclass

from src.llm.nebius_client import get_llm, invoke_json  # adjust import path once client file is placed


@dataclass
class SecurityFinding:
    module: str
    issue: str
    severity: str  # "low" | "medium" | "high"
    reasoning: str


SECURITY_PROMPT = """You are reviewing Terraform for security risk,
including both clear misconfigurations and context-dependent
judgment calls. Known deterministic issues already checked
separately are: missing version-constraint blocks, deprecated
resource arguments, deprecated instance types, and missing deletion
protection on stateful resources — do not re-report those specific
categories. Discrepancies between code comments and actual resource
configuration are a SEPARATE documentation-drift concern, checked
elsewhere — do not report those here, only report risk arising from
the actual resource configuration itself.

Specifically check for, in addition to anything else you notice:
- Overly permissive network access (open CIDR ranges, unrestricted ports)
- Missing or weak encryption settings
- Missing public-access blocking on storage resources

Module: {module_name}

{resource_text}

Respond ONLY with valid JSON, no other text, always as an object with
a "findings" key (never a bare list):
{{"findings": [{{"issue": "...", "severity": "low"|"medium"|"high", "reasoning": "one sentence, max 20 words"}}]}}
If there are no findings, return {{"findings": []}}.
"""

def check_module_security(module_name: str, resource_text: str) -> list[SecurityFinding]:
    llm = get_llm(max_tokens=8192, temperature=0.1, frequency_penalty=0.4)
    prompt = SECURITY_PROMPT.format(module_name=module_name, resource_text=resource_text)
    result = invoke_json(llm, prompt)

    if isinstance(result, dict) and "_error" in result:
        return [SecurityFinding(
            module=module_name,
            issue="LLM_CALL_FAILED",
            severity="unknown",
            reasoning=result["_error"],
        )]

    # Defend against the LLM returning a bare list (e.g. `[]` or
    # `[{...}]`) instead of the requested {"findings": [...]} wrapper
    # shape — observed for real on vpc-base during eval runs. Treat a
    # bare list as if it WERE the findings list directly, rather than
    # crashing with 'list' object has no attribute 'get'.
    if isinstance(result, list):
        findings_data = result
    elif isinstance(result, dict):
        findings_data = result.get("findings", [])
    else:
        # Some other unexpected shape entirely — surface it rather
        # than silently returning [] and hiding a real parsing gap.
        return [SecurityFinding(
            module=module_name,
            issue="UNEXPECTED_RESPONSE_SHAPE",
            severity="unknown",
            reasoning=f"invoke_json returned type {type(result).__name__}, expected dict or list",
        )]

    return [
        SecurityFinding(
            module=module_name,
            issue=f["issue"],
            severity=f["severity"],
            reasoning=f["reasoning"],
        )
        for f in findings_data
    ]