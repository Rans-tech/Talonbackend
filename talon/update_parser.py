import re

# Read the file
with open('document_parser.py', 'r') as f:
    content = f.read()

# Define the new method to add
pdf_method = '''
    def _extract_pdf_images(self, pdf_content_base64):
        """
        Extract images from PDF pages for Vision API processing

        Args:
            pdf_content_base64: Base64 encoded PDF content

        Returns:
            list: List of base64 encoded PNG images (one per page)
        """
        if not PDF_SUPPORT:
            return None

        try:
            # Decode base64 PDF content
            pdf_bytes = base64.b64decode(pdf_content_base64)

            # Open PDF with PyMuPDF
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")

            images = []
            # Convert each page to image (limit to first 5 pages for performance)
            for page_num in range(min(len(doc), 5)):
                page = doc[page_num]
                # Render page to image (300 DPI for good quality)
                pix = page.get_pixmap(matrix=fitz.Matrix(300/72, 300/72))

                # Convert to PNG bytes
                img_bytes = pix.tobytes("png")

                # Convert to base64
                img_base64 = base64.b64encode(img_bytes).decode('utf-8')
                images.append(img_base64)

            doc.close()
            return images

        except Exception as e:
            print(f"Error extracting PDF images: {e}")
            return None

'''

# Find the end of _load_knowledge_base and insert before parse_travel_document
old_text = '''            return {}

    def parse_travel_document'''

new_text = '''            return {}
''' + pdf_method + '''    def parse_travel_document'''

new_content = content.replace(old_text, new_text)

# Write back
with open('document_parser.py', 'w') as f:
    f.write(new_content)

print("Done")
