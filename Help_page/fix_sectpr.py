"""
Fix the document.xml so that <w:sectPr> is the last element in <w:body>.
Any <w:p> paragraphs that were inserted after <w:sectPr> should be moved before it.
"""

DOC_PATH = r'C:\Users\75BD~1\AppData\Local\Temp\part1_unpacked\word\document.xml'

with open(DOC_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

# Find sectPr start and end
sectr_start = content.find('<w:sectPr ')
sectr_end = content.find('</w:sectPr>') + len('</w:sectPr>')

if sectr_start == -1 or sectr_end == -1:
    print("ERROR: Could not find sectPr")
    exit(1)

print(f"sectPr found at chars {sectr_start} to {sectr_end}")

# Extract what's between sectPr end and </w:body>
body_close = content.rfind('</w:body>')
if body_close == -1:
    print("ERROR: Could not find </w:body>")
    exit(1)

# Content after </w:sectPr> and before </w:body>
after_sectr = content[sectr_end:body_close]
print(f"Content after sectPr (before </w:body>): {len(after_sectr)} chars")

# The sectPr itself
sectr_block = content[sectr_start:sectr_end]

# Content before sectPr
before_sectr = content[:sectr_start]

# Reconstruct: before_sectr + after_sectr (the glossary paragraphs) + sectr_block + </w:body>...
new_content = before_sectr + after_sectr + '\n' + sectr_block + '\n' + content[body_close:]

# Verify sectPr is now last
new_sectr_pos = new_content.find('<w:sectPr ')
new_body_close = new_content.rfind('</w:body>')
new_sectr_end = new_content.find('</w:sectPr>') + len('</w:sectPr>')

print(f"After fix: sectPr ends at {new_sectr_end}, body close at {new_body_close}")

# Check nothing is between sectPr end and body close (just whitespace)
between = new_content[new_sectr_end:new_body_close].strip()
print(f"Between sectPr and body close: '{between[:100]}'")

if between == '':
    print("OK: sectPr is now the last element before </w:body>")
else:
    print(f"WARNING: Still content between sectPr and body: {between[:200]}")

with open(DOC_PATH, 'w', encoding='utf-8') as f:
    f.write(new_content)

print(f"Done. New size: {len(new_content)}")
