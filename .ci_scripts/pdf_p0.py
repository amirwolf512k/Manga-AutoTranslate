import sys

import fitz

key = sys.argv[1]
doc = fitz.open(f"/tmp/emulout6/{key}.pdf")
pix = doc[0].get_pixmap(dpi=110)
pix.save(f"/tmp/emulout6/{key}_p0.jpg")
print(f"[✓] {key} pdf page0 rendered: {pix.width}x{pix.height}")
