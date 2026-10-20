"""Turning a report into a file: a CSV for a spreadsheet, a PDF for the office.

Both exports take the same headings and rows the screen shows, so the file can never
disagree with the table it came from. The PDF is written by hand — a landscape A4 page
of fixed-width text — because the app has no room for a typesetting library.
"""

import csv
import io
import re

# A landscape A4 page, in points.
PAGE_WIDTH = 842
PAGE_HEIGHT = 595
MARGIN = 24
FONT_SIZE = 6
LEADING = 10

# How many characters of that font fit across the page's live area.
COLUMNS = 200


def csv_bytes(headings: list[str], rows: list[list[str]]) -> bytes:
    """The sheet as comma-separated text."""
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(headings)
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def pdf_bytes(
    title: str, month: str, sheet: str, headings: list[str], rows: list[list[str]]
) -> bytes:
    """The sheet as a printable landscape page, with its own title block."""
    lines = _layout(headings, rows)
    return _document(_content(title, month, sheet, lines))


def file_name(sheet: str, month: str, extension: str) -> str:
    """The default name a save dialog offers: `icds-sabji-bill-march-2026.csv`."""
    return f"icds-{_slug(sheet)}-{_slug(month)}.{extension}"


def _slug(value: str) -> str:
    """A name a file system, and the office, both accept."""
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _layout(headings: list[str], rows: list[list[str]]) -> list[str]:
    """The sheet as monospaced lines: a heading, a rule, then every row."""
    widths = _widths(headings, rows)
    return [
        _line(headings, widths),
        "-" * sum(widths),
        *[_line(row, widths) for row in rows],
    ]


def _widths(headings: list[str], rows: list[list[str]]) -> list[int]:
    """A share of the page per column, squeezed evenly when the sheet is wide."""
    wanted = [
        max(len(heading), *(len(row[index]) for row in rows)) + 2
        for index, heading in enumerate(headings)
    ]
    total = sum(wanted)
    if total <= COLUMNS:
        return wanted
    return [max(7, int(width * COLUMNS / total)) for width in wanted]


def _line(values: list[str], widths: list[int]) -> str:
    """One line of the table: numbers to the right of their column, names left."""
    cells = [
        value[: width - 1].rjust(width)
        if _numeric(value)
        else value[: width - 1].ljust(width)
        for value, width in zip(values, widths, strict=True)
    ]
    return "".join(cells).rstrip()


def _numeric(value: str) -> bool:
    """Whether a cell is a figure, which the paper sets to the right."""
    try:
        float(value)
    except ValueError:
        return False
    return bool(value)


def _content(title: str, month: str, sheet: str, lines: list[str]) -> bytes:
    """The page's text: a title block, then the sheet."""
    top = PAGE_HEIGHT - MARGIN - 12
    text = [
        _text(f"{title} — {sheet}", "F2", 12, MARGIN, top),
        _text(month, "F1", 9, MARGIN, top - 16),
        _text("", "F1", FONT_SIZE, MARGIN, top - 34),
        f"BT /F1 {FONT_SIZE} Tf {LEADING} TL {MARGIN} {top - 34} Td",
        *[f"({_escape(line)}) Tj T*" for line in lines],
        "ET",
    ]
    return "\n".join(text).encode("cp1252", "replace")


def _text(value: str, font: str, size: int, x: int, y: int) -> str:
    """One line of text, placed on the page."""
    return f"BT /{font} {size} Tf {x} {y} Td ({_escape(value)}) Tj ET"


def _escape(value: str) -> str:
    """A PDF string literal cannot carry brackets or a backslash unescaped."""
    return value.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def _document(stream: bytes) -> bytes:
    """Wrap a content stream in a single-page PDF, with its cross-reference table."""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
            "/Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> /Contents 4 0 R >>"
        ).encode("ascii"),
        b"<< /Length "
        + str(len(stream)).encode("ascii")
        + b" >>\nstream\n"
        + stream
        + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold "
        b"/Encoding /WinAnsiEncoding >>",
    ]

    page = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(page))
        page += f"{number} 0 obj\n".encode("ascii") + body + b"\nendobj\n"

    start = len(page)
    page += f"xref\n0 {len(objects) + 1}\n".encode("ascii")
    page += b"0000000000 65535 f \n"
    for offset in offsets:
        page += f"{offset:010d} 00000 n \n".encode("ascii")
    page += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{start}\n"
        "%%EOF\n"
    ).encode("ascii")
    return bytes(page)
