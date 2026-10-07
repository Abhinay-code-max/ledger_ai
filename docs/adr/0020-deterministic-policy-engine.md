# ADR 0020: Deterministic policy engine

Status: Accepted

Policies are immutable published sets of ordered rules over allowlisted typed inputs and operators.
The highest matching priority wins, with strictest-outcome resolution for ties; no match safely
requires review. Decisions persist inputs and version metadata. Executable Python, SQL, templates,
regex, shell, dynamic imports, and model-supplied rules are excluded so historical outcomes can be
reproduced without executing untrusted content.
