import os
import unicodedata
from datetime import datetime
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from config import OUTPUTS_DIR, NEWSPAPER_NAME, NEWSPAPER_TAGLINE


# Characters the built-in PDF fonts (Helvetica / Times) can't draw -> safe replacements
CHAR_REPLACEMENTS = {
    "\u2010": "-",    # hyphen
    "\u2011": "-",    # non-breaking hyphen (the black squares)
    "\u2012": "-",    # figure dash
    "\u2212": "-",    # minus sign
    "\u00a0": " ",    # non-breaking space
    "\u202f": " ",    # narrow no-break space
    "\u2009": " ",    # thin space
    "\u200a": " ",    # hair space
    "\u2002": " ",    # en space
    "\u2003": " ",    # em space
    "\u200b": "",     # zero-width space
    "\u200c": "",     # zero-width non-joiner
    "\u200d": "",     # zero-width joiner
    "\u2060": "",     # word joiner
    "\ufeff": "",     # byte order mark
    "\u2192": "->",   # right arrow
    "\u2190": "<-",   # left arrow
    "\u2248": "~",    # approx equal
    "\u2264": "<=",   # less or equal
    "\u2265": ">=",   # greater or equal
    "\u2713": "",     # check mark
}


def sanitize_text(text) -> str:
    """
    Makes text safe for ReportLab's built-in fonts:
    1. replaces known problem characters,
    2. keeps anything the font can draw (cp1252),
    3. converts accented/odd characters to plain equivalents when possible,
    4. drops whatever is left so no black squares appear.
    """
    if text is None:
        return ""
    text = str(text)

    for old, new in CHAR_REPLACEMENTS.items():
        text = text.replace(old, new)

    cleaned = []
    for ch in text:
        try:
            ch.encode("cp1252")
            cleaned.append(ch)
        except UnicodeEncodeError:
            ascii_equiv = unicodedata.normalize("NFKD", ch).encode("ascii", "ignore").decode("ascii")
            cleaned.append(ascii_equiv)  # empty string if no equivalent
    return "".join(cleaned)


def safe_para_text(text) -> str:
    """Sanitize, then escape &, <, > so ReportLab's mini-markup doesn't choke."""
    return escape(sanitize_text(text))


class BroadsheetPDFBuilder:
    def __init__(self, edition_title: str = NEWSPAPER_NAME):
        self.edition_title = edition_title
        self.page_size = A4  # Width: 595.27 pt, Height: 841.89 pt

    def generate_pdf(self, articles: list, filename: str = None) -> str:
        """
        Compiles synthesized articles into a multi-column broadsheet newspaper PDF.
        """
        if not filename:
            date_str = datetime.now().strftime("%Y-%m-%d")
            filename = f"edition_{date_str}.pdf"

        filepath = os.path.join(OUTPUTS_DIR, filename)

        # Setup document margins (narrower margins for newspaper density)
        doc = SimpleDocTemplate(
            filepath,
            pagesize=self.page_size,
            leftMargin=30,
            rightMargin=30,
            topMargin=30,
            bottomMargin=30
        )

        styles = getSampleStyleSheet()

        # Custom Newspaper Styles
        title_style = ParagraphStyle(
            'NewsMasthead',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=32,
            leading=36,
            alignment=1,  # Centered
            textColor=colors.HexColor('#0A0A0A')
        )

        tagline_style = ParagraphStyle(
            'NewsTagline',
            parent=styles['Normal'],
            fontName='Helvetica-Oblique',
            fontSize=10,
            leading=12,
            alignment=1,
            textColor=colors.HexColor('#4A4A4A')
        )

        headline_style = ParagraphStyle(
            'ArticleHeadline',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=14,
            leading=16,
            textColor=colors.HexColor('#111111'),
            spaceAfter=6
        )

        body_style = ParagraphStyle(
            'ArticleBody',
            parent=styles['Normal'],
            fontName='Times-Roman',
            fontSize=9.5,
            leading=12,
            textColor=colors.HexColor('#222222'),
            alignment=4  # Justified like a real newspaper
        )

        dialectic_style = ParagraphStyle(
            'DialecticBox',
            parent=styles['Normal'],
            fontName='Helvetica-Oblique',
            fontSize=9,
            leading=11,
            textColor=colors.HexColor('#333333')
        )

        kicker_style = ParagraphStyle(
            'Kicker',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=8,
            leading=9,
            textColor=colors.HexColor('#555555')
        )

        story = []

        # 1. Newspaper Masthead Header
        story.append(Paragraph(safe_para_text(self.edition_title), title_style))
        story.append(Spacer(1, 4))
        story.append(Paragraph(
            f"{safe_para_text(NEWSPAPER_TAGLINE)} &bull; {datetime.now().strftime('%A, %B %d, %Y')}",
            tagline_style
        ))
        story.append(Spacer(1, 10))
        story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#000000'), spaceAfter=15))

        # 2. Populate Articles in a Multi-Column Layout Grid
        for article in articles:
            headline_text = safe_para_text(article.get("headline", "Untitled Brief"))
            summary_text = safe_para_text(article.get("summary", ""))
            dialectic_text = safe_para_text(article.get("dialectic_perspective", ""))
            category = safe_para_text(article.get("category", "General"))

            # Category kicker + headline
            story.append(Paragraph(category.upper(), kicker_style))
            story.append(Paragraph(headline_text, headline_style))

            # Main summary and dialectic column layout using a 2-column table
            summary_para = Paragraph(summary_text, body_style)
            dialectic_para = Paragraph(f"<b>Dialectic Context:</b><br/>{dialectic_text}", dialectic_style)

            # Pack into a structured newspaper column table with a vertical divider border
            col_table = Table([[summary_para, dialectic_para]], colWidths=[270, 260])
            col_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LINEBEFORE', (1, 0), (1, 0), 0.5, colors.HexColor('#CCCCCC')),
                ('LEFTPADDING', (1, 0), (1, 0), 10),
                ('RIGHTPADDING', (0, 0), (0, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ]))

            story.append(col_table)
            story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#DDDDDD'), spaceAfter=10))

        # Build PDF Document
        doc.build(story)
        return filepath