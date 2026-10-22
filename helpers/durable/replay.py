"""Explicit source-pinned replay audits; drift requires a new review."""

AUDITED_HOOKS = {
    ('BrowserModelCleanup', '55ad6654cf45adc77f741cfa7e47e0562fa5a3bcc6768f7527af95e00d0a2f6d'),
    ('WaitingForInputMsg', '6c783e2e86031a26d33ed50204fbeb28004e1813618f9eb5851e98f2a69712d5'),
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

# Constructor recovery may only repeat these local projection/config readers.
AUDITED_INIT_HOOKS = {
    ('InitialMessage', '6f481bc1336f0ff03ba63813a4acc12658322ca4576ca59ce26d9af3c618c7df'),
    ('LoadProfileSettings', 'bcdb72dd58bf73787ec480de4c9044769b78d563d156dde91988d57e6be09589'),
}

AUDITED_INITIAL_HISTORY_HOOKS = {
    ('MaskHistoryContent', 'eb613a29492b4e9fa9b238de709d3fcee747b7ab6dee78e7871b0371dafb3f41'),
    ('LogPlainResponses', '8e560915a78d34ae28f3d8ca6ef9e2f39cb2af6ad794174eb37626f000d46b2d'),
}

# These continuations are safe only with the shared detached broker enabled.
BROKER_HOOKS = {
    ('tool_execute_before', 'InfectionAwaitCheck', '512b014e0a35414b13099dc4054ce087be31a4a5a28a59c616de7468a8486dd8'),
    ('monologue_end', 'MemorizeMemories', '23cb02117e10c8eb9660ae717db99263456ee5fca5ee1c83356298bafc60c027'),
    ('monologue_end', 'MemorizeSolutions', 'b81bc8cef9fa1dae758ed2b48c54527846a42f104ffeb22e976e5fda86a81414'),
    ('message_loop_end', 'OrganizeHistory', '5626c794a2cfae39119499fa7696f41fed4d2a765afb3b816eb1df02d92dc7c6'),
}
