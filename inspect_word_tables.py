import docx

doc = docx.Document("e:/uzbiznesss_site/template.docx")
for i, table in enumerate(doc.tables):
    print(f"\n--- Table {i+1} ---")
    for r_idx, row in enumerate(table.rows):
        row_vars = []
        for c_idx, cell in enumerate(row.cells):
             if "{{" in cell.text:
                  row_vars.append(f"Col {c_idx+1}: {cell.text.strip()}")
        if row_vars:
             print(f"Row {r_idx+1}:", " | ".join(row_vars))

