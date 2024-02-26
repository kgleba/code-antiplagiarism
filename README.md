# Code Antiplagiarism Project

Usage: `python main.py files [-e EXCLUDE] (-q | -d | --double-layer COEFFICIENT) [-o OUTPUT]`

**-q, --quick** – quick check (without comparing ASTs)

**-d, --detailed** – detailed check (with comparing ASTs)

**--double-layer** – selective check (with comparing AST on the significant results of quick check)

**-e, --exclude** – exclude specified patterns

**-o, --output** – file to output program's runtime result, console by default
