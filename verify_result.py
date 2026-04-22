
import docx
from docx.oxml.table import CT_Tbl

doc = docx.Document('d:/uzbiznesss_site/test_word.docx')
body = doc.element.body

print(f"Total internal elements: {len(body)}")
for i in range(130, min(160, len(body))):
    el = body[i]
    tag = el.tag.split('}')[-1]
    text = ""
    if tag == 'p':
        text = el.text[:100]
    elif tag == 'tbl':
        # Get first cell text
        try:
            text = "TABLE: " + el.xpath('.//w:t')[0].text
        except:
            text = "TABLE (empty or complex)"
    
    print(f"{i:3}: {tag:5} | {text}")
