"""Pure functions used by ingestion workers — no I/O, no DB.

`wiki_compiler` builds the LLM prompt and parses the YAML response.
`chapter_splitter` slices Docling markdown by `chapters[].page_range`.

These functions are deliberately I/O-free so workers can call them without
binding the algorithm to the worker scaffolding.
"""
