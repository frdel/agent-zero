### biomedical_data_loader:
load and process biomedical datasets from multiple sources
supports genomics (TCGA, NCBI, Ensembl), proteomics (UniProt), clinical, imaging, literature data
automated format conversion and quality processing
usage:
~~~json
{
    "thoughts": [
        "User needs to load TCGA breast cancer genomics data...",
        "I should specify normalization and quality filtering options...",
    ],
    "headline": "Loading biomedical dataset with processing options",
    "tool_name": "biomedical_data_loader",
    "tool_args": {
        "data_type": "genomics",
        "source": "TCGA",
        "file_path": "/data/tcga_brca_2024.maf",
        "load_options": {
            "normalize": true,
            "filter_quality": true,
            "include_variants": true
        }
    }
}
~~~