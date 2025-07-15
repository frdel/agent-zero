### sequence_analyzer:
comprehensive DNA RNA protein sequence analysis
bioinformatics sequence manipulation annotation translation
**Parameters:**
- sequence: input sequence (DNA, RNA, or protein)
- sequence_type: type of sequence ("auto", "dna", "rna", "protein")
- analysis_type: analysis depth ("basic", "detailed", "comprehensive")
- reference_genome: reference genome ("hg38", "hg19", "mm10")
- annotation_level: annotation level ("basic", "detailed", "comprehensive")
- include_translation: include translation analysis (default true)
- find_orfs: find open reading frames (default true)
- search_motifs: search for sequence motifs (default true)

**Example usage:**
~~~json
{
    "thoughts": [
        "I need to analyze this DNA sequence for potential coding regions",
    ],
    "headline": "Analyzing DNA sequence for coding potential",
    "tool_name": "sequence_analyzer",
    "tool_args": {
        "sequence": "ATGAAACGCATTAGCACCACCATTACCACCACCATCACCATTACCACAGGTAACGGTGCGGGCTGA",
        "sequence_type": "dna",
        "analysis_type": "comprehensive",
        "include_translation": true,
        "find_orfs": true,
        "search_motifs": true
    }
}
~~~