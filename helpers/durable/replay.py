"""Explicit source-pinned replay audits; drift requires a new review."""

AUDITED_HOOKS = {
    ('MaskReasoningStreamEnd', '55eae68432367201f292a4bdd13527519d763f45b2247a20cb09901619d3c872'),
    ('MaskResponseStreamEnd', '5f7fa3c82c5d468fd680127251a50d3cc189153c55e1c10d038635619eab035d'),
    ('LogFromStream', '658d4be2120b4914872941d9e8c17141f9a7f852100d8a4114f34695a2adc9ed'),
    ('ReplaceLastToolOutput', 'c309d8f1eb104a01dece04e4f63026881abb49bf220387ae46f4598ce2e847ea'),
    ('UnmaskToolSecrets', '9b8e435be74e6a6d41718fa1de7fe0ff43f5a929da7f0d98e46521f6a8965941'),
    ('BlockParallelRecursion', '5eff30bc40ccee527217a79ec08403b138440b64c62f48294725eb2875a46959'),
    ('MaskToolSecrets', 'c37ca95db6bc9c62af50a69a430f111a48d507b49b66a53a80a9eab513a12115'),
    ('EnforceToolPolicy', '814c5974e8f0d647d75974cbc7479ad8b0edf67783f45ba5c6c80726f107164f'),
}

AUDITED_TOOLS = {
    ('DurablePlan', '679ab1311cd1dd95eb3cce80d75c15eb8a6ea7029a19fb2c44bee2780599cec5'),
    ('ResponseTool', '805ca9cedf2465f5fb42b2255fa04c385c7ef7acf2df0aea32455041ce451422'),
}

# Exact built-in workflow sources are pinned after adapter verification.
AUDITED_WORKFLOWS = {
    ('Delegation', '631918e65e9e189912c9f264160ab8b10ac2a79a9d0f1e7db3a6b30410837bd2'),
    ('ParallelTool', '7e6c3aef4de60b02e483d1e7d862f9dcf5a3f7adf36ff75803625bb8317d8904'),
}
