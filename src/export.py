"""Turning a report into a file: a CSV for a spreadsheet, a PDF for the office.

Both exports take the same headings and rows the screen shows, so the file can never
disagree with the table it came from. The PDF is written by hand — landscape A4 pages
of fixed-width text — because the app has no room for a typesetting library. A sheet
wider than the page is split into column runs, and every page repeats the date column
and the headings, so nothing is shrunk or cut to fit.
"""

import csv
import io
import re

# A landscape A4 page, in points.
PAGE_WIDTH = 842
PAGE_HEIGHT = 595
MARGIN = 28
FONT_SIZE = 9
LEADING = 13

# The room the title block takes above the table, in points.
TITLE_HEIGHT = 56

# How many characters of that font fit across the page's live area.
COLUMNS = 144

# The date column is repeated on every page; a figure column never grows past this.
MAX_COLUMN = 60


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
    """The sheet as printable landscape pages, with its own title block."""
    return _document(_pages(title, month, sheet, headings, rows))


def file_name(sheet: str, month: str, extension: str) -> str:
    """The default name a save dialog offers: `icds-sabji-bill-march-2026.csv`."""
    return f"icds-{_slug(sheet)}-{_slug(month)}.{extension}"


def _slug(value: str) -> str:
    """A name a file system, and the office, both accept."""
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _widths(headings: list[str], rows: list[list[str]]) -> list[int]:
    """A natural width per column: its longest value with a margin, up to a cap."""
    return [
        min(MAX_COLUMN, max([len(heading), *(len(row[index]) for row in rows)]) + 2)
        for index, heading in enumerate(headings)
    ]


def _column_groups(widths: list[int]) -> list[list[int]]:
    """The figure columns split into runs that fit beside the date on one page.

    The date is the first column and is repeated on every page; the figure columns
    are packed greedily in sheet order so a run never has to be squeezed.
    """
    room = COLUMNS - widths[0]
    groups: list[list[int]] = []
    current: list[int] = []
    used = 0
    for index in range(1, len(widths)):
        width = widths[index]
        if current and used + width > room:
            groups.append(current)
            current, used = [], 0
        current.append(index)
        used += width
    if current:
        groups.append(current)
    return groups or [[]]


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


def _pages(
    title: str, month: str, sheet: str, headings: list[str], rows: list[list[str]]
) -> list[bytes]:
    """One content stream per page: a column run, split again if it runs long.

    Each page carries its own heading and rule, so a figures page read on its own
    still says what its columns are. The date column travels with every run.
    """
    widths = _widths(headings, rows)
    room = _room()
    blocks: list[tuple[list[int], list[str]]] = []
    for group in _column_groups(widths):
        chosen = [0, *group]
        lines = [
            _line([row[index] for index in chosen], [widths[index] for index in chosen])
            for row in rows
        ]
        for start in range(0, max(len(lines), 1), room):
            blocks.append((chosen, lines[start : start + room]))
    total = len(blocks)
    return [
        _content(title, month, sheet, headings, widths, chosen, lines, number, total)
        for number, (chosen, lines) in enumerate(blocks, start=1)
    ]


def _room() -> int:
    """How many table lines fit between the title block and the bottom margin."""
    return (PAGE_HEIGHT - 2 * MARGIN - TITLE_HEIGHT) // LEADING - 2


def _content(
    title: str,
    month: str,
    sheet: str,
    headings: list[str],
    widths: list[int],
    chosen: list[int],
    lines: list[str],
    number: int,
    total: int,
) -> bytes:
    """One page's text: a title block, the column headings, then the rows."""
    top = PAGE_HEIGHT - MARGIN
    lead = _line(
        [headings[index] for index in chosen], [widths[index] for index in chosen]
    )
    rule = "-" * sum(widths[index] for index in chosen)
    text = [
        _text(f"{title} — {sheet}", "F2", 14, MARGIN, top - 14),
        _text(f"{month} · Page {number} of {total}", "F1", 9, MARGIN, top - 36),
        f"BT /F1 {FONT_SIZE} Tf {LEADING} TL {MARGIN} {top - TITLE_HEIGHT} Td",
        *[f"({_escape(line)}) Tj T*" for line in (lead, rule, *lines)],
        "ET",
    ]
    return "\n".join(text).encode("cp1252", "replace")


def _text(value: str, font: str, size: int, x: int, y: int) -> str:
    """One line of text, placed on the page."""
    return f"BT /{font} {size} Tf {x} {y} Td ({_escape(value)}) Tj ET"


def _escape(value: str) -> str:
    """A PDF string literal cannot carry brackets or a backslash unescaped."""
    return value.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def _document(pages: list[bytes]) -> bytes:
    """Wrap each content stream in its own page, with one cross-reference table."""
    first_page = 3
    kids = " ".join(f"{first_page + 2 * index} 0 R" for index in range(len(pages)))
    courier = 3 + 2 * len(pages)
    bold = courier + 1
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode("ascii"),
    ]
    for stream in pages:
        number = len(objects) + 1
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
                f"/Resources << /Font << /F1 {courier} 0 R /F2 {bold} 0 R >> >> "
                f"/Contents {number + 1} 0 R >>"
            ).encode("ascii")
        )
        objects.append(
            b"<< /Length "
            + str(len(stream)).encode("ascii")
            + b" >>\nstream\n"
            + stream
            + b"\nendstream"
        )
    objects.append(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>"
    )
    objects.append(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold "
        b"/Encoding /WinAnsiEncoding >>"
    )

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
