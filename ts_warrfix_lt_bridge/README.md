v9: monkey-patch action_update_stock and create_sap_doc to ensure LT bridge runs.


- v13: LT inventory now prefers paired warehouse code (e.g. HCMVP220 -> HCMVP201) and falls back to current warehouse only when pairing cannot be derived.
