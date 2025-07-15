### molecular_docking:
molecular docking simulation for drug discovery
protein-ligand interaction analysis binding affinity prediction
**Parameters:**
- target_protein: protein target (PDB ID, UniProt ID, or name)
- ligand_compound: ligand compound (SMILES, name, or ChEMBL ID)
- binding_site: binding site specification (coordinates or site name)
- docking_method: docking method ("rigid", "flexible", "induced_fit")
- scoring_function: scoring function ("vina", "autodock", "glide", "chemplp")
- num_poses: number of binding poses (1-50, default 10)
- energy_range: energy range for poses (kcal/mol, default 3.0)
- analyze_interactions: analyze protein-ligand interactions (default true)

**Example usage:**
~~~json
{
    "thoughts": [
        "I need to dock aspirin to COX-2 to analyze binding interactions",
    ],
    "headline": "Performing molecular docking of aspirin to COX-2",
    "tool_name": "molecular_docking",
    "tool_args": {
        "target_protein": "1a4k",
        "ligand_compound": "aspirin",
        "docking_method": "flexible",
        "scoring_function": "vina",
        "num_poses": 20,
        "analyze_interactions": true
    }
}
~~~