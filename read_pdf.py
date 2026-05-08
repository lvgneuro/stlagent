import pdfplumber

pdf = pdfplumber.open("E:/ТГ-агент/Калинка МФ/ТО Калинка 72.pdf")
text = ""
for i, page in enumerate(pdf.pages):
    t = page.extract_text()
    if t:
        text += f"\n---PAGE {i + 1}---\n" + t
print(text[:3000])
