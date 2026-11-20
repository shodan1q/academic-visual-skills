# Academic Visual Skills

Nine instruction-first Agent Skills for academic figures and slides. Each directory is a self-contained Skill
(`SKILL.md` + small stdlib Python helpers + checklist + examples + design notes). Load a directory as a Skill;
the agent reads the case materials, writes editable sources (SVG / matplotlib / PPTX) with real rendered
previews, keeps a source map for every number and label, and fills `result.json` with an honest status.

| Dir | Purpose |
|---|---|
| `01-graphical-abstract` | Graphical abstract from a paper |
| `02-schematic` | Method / mechanism schematic |
| `03-data-chart` | Data chart from CSV/XLSX with data-to-mark check |
| `04-pathway` | Signalling / reaction pathway diagram |
| `05-apparatus-route` | Apparatus or synthesis-route figure |
| `06-paper2ppt` | Paper → slide deck |
| `07-talk-organize` | Organise talk materials into a deck |
| `08-template-adapt` | Adapt content to a given PPTX template |
| `09-deck-edit` | Revise an existing deck with a change log |

Requirements: Python 3.8+ standard library. matplotlib, python-pptx, cairosvg, rsvg-convert, inkscape and
LibreOffice are used when present and skipped with a note when absent.

License: MIT
