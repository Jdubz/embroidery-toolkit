# Brother manuals — not distributed here

The toolkit and docs lean on these heavily, and `CLAUDE.md` tells you to grep
them before searching the web. They are **not in this repository**: they are
Brother Industries' copyrighted material, and republishing them is not ours to
do. `.gitignore` excludes them so they cannot be committed by accident.

Download them from Brother's own support site and drop them in this folder.
Search the SE700 product page for Manuals:

<https://support.brother.com/g/b/productsearch.aspx?c=us&lang=en&content=ml>

| File this repo expects | Brother's name for it |
|---|---|
| `SE700-Operation-Manual-EN.pdf` | Operation Manual |
| `SE700-Quick-Reference-Guide.pdf` | Quick Reference Guide |
| `SE700-Embroidery-Design-Guide.pdf` | Embroidery Design Guide |
| `Design-Database-Transfer-Instruction-Manual.pdf` | Design Database Transfer Instruction Manual |

The tooling greps **text extractions**, not the PDFs, so make one per manual
with the same basename and a `.txt` extension:

```powershell
.venv\Scripts\python.exe -c "import pypdf,sys; p=pypdf.PdfReader(sys.argv[1]); open(sys.argv[2],'w',encoding='utf-8').write('\n'.join(f'===PAGE {i+1}===\n'+(pg.extract_text() or '') for i,pg in enumerate(p.pages)))" SE700-Operation-Manual-EN.pdf SE700-Operation-Manual-EN.txt
```

The `===PAGE n===` markers matter — page numbers are cited throughout `docs/`
and in `CLAUDE.md` (embroidery tension p.72, error messages p.93, the
"Upper thread tightened up" entry on p.85, and so on).

Without these files, everything still builds and validates; you just lose the
ability to check a claim against the manual, which is the repo's habit for
anything about how the machine behaves.

Thread charts under `reference/charts/` are excluded for the same reason.
`brother-pec-thread-palette.csv` **is** included — it is the 64-entry PEC
palette, derived data the toolkit needs to function rather than a copy of
Brother's document.
