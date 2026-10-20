"""The design's tokens: colour, type, space, shape and shadow.

Every screen reads its look from here, so a palette or type change is a change to
this file alone. The names are the design document's names, kept semantic so a
future palette swap touches no screen.
"""

import dataclasses

import flet as ft

# Brand and primary
PRIMARY_700 = "#0F55B8"
PRIMARY_600 = "#1667D9"
PRIMARY_500 = "#2F7BEF"
PRIMARY_100 = "#DCE9FB"
PRIMARY_050 = "#EEF5FE"

# Surfaces and structure
CANVAS = "#F1F5FB"
SURFACE = "#FFFFFF"
SURFACE_MUTED = "#F8FAFD"
TABLE_HEADER = "#E9EFF9"
BORDER_SUBTLE = "#E6EBF3"
BORDER_STRONG = "#CBD5E3"

# Text
TEXT = "#101828"
TEXT_SECONDARY = "#5A6B85"
TEXT_TERTIARY = "#8494AB"
TEXT_INVERSE = "#FFFFFF"

# The two head groups
MOTHER_BAND = "#F7CBE1"
MOTHER_BG = "#FBDCEC"
MOTHER_INK = "#C2185B"
CHILDREN_BAND = "#CBEBD6"
CHILDREN_BG = "#DDF2E4"
CHILDREN_INK = "#12703F"

# A closed day
CLOSED_ROW = "#FDEDEF"
CLOSED_FIELD = "#FBE3E7"
CLOSED_INK = "#C62828"

# Status
DANGER = "#D92D42"
WARNING = "#DE8F16"
SUCCESS = "#12703F"

# Pastel icon tiles: a background and the ink that reads on it.
BLUE = ("#E4F0FD", "#1B6FD4")
MINT = ("#DDF3E7", "#17784B")
PINK = ("#FCE4EE", "#D6467F")
AMBER = ("#FFF0D6", "#DE8F16")
NEUTRAL = ("#EEF2F8", "#5A6B85")

# Space, on the 4 dp scale
SPACE_1 = 4
SPACE_2 = 8
SPACE_3 = 12
SPACE_4 = 16
SPACE_5 = 20
SPACE_6 = 24
SPACE_8 = 32

# Shape
RADIUS_CARD = 20
RADIUS_FIELD = 10
RADIUS_BAND = 12
RADIUS_PILL = 999

# How wide the content column is allowed to grow before it is centred.
CONTENT_WIDTH = 720

# Type roles
PAGE_TITLE = ft.TextStyle(
    size=30, weight=ft.FontWeight.W_800, color=TEXT, letter_spacing=-0.4
)
PAGE_SUBTITLE = ft.TextStyle(size=15, color=TEXT_SECONDARY)
CARD_TITLE = ft.TextStyle(
    size=21, weight=ft.FontWeight.W_700, color=TEXT, letter_spacing=-0.2
)
CARD_SUBTITLE = ft.TextStyle(size=14, color=TEXT_SECONDARY)
SECTION_TITLE = ft.TextStyle(size=16, weight=ft.FontWeight.W_700, color=TEXT)
GROUP_HEADER = ft.TextStyle(size=14, weight=ft.FontWeight.W_700, color=TEXT)
COLUMN_HEADER = ft.TextStyle(size=13, weight=ft.FontWeight.W_600, color=TEXT_SECONDARY)
CELL = ft.TextStyle(size=16, weight=ft.FontWeight.W_500, color=TEXT)
TOTAL_LABEL = ft.TextStyle(size=15, weight=ft.FontWeight.W_700, color=TEXT)
TOTAL_VALUE = ft.TextStyle(size=16, weight=ft.FontWeight.W_700, color=TEXT)
FIELD = ft.TextStyle(size=16, weight=ft.FontWeight.W_500, color=TEXT)
CHIP_DATE = ft.TextStyle(size=22, weight=ft.FontWeight.W_700, color=PRIMARY_600)
CHIP_MONTH = ft.TextStyle(
    size=12, weight=ft.FontWeight.W_500, color=TEXT_SECONDARY, letter_spacing=0.4
)
CHIP_WEEKDAY = ft.TextStyle(size=15, weight=ft.FontWeight.W_500, color=TEXT_SECONDARY)
BUTTON = ft.TextStyle(size=17, weight=ft.FontWeight.W_600)
STEP_LABEL = ft.TextStyle(size=12, weight=ft.FontWeight.W_500, color=TEXT_SECONDARY)
STEP_LABEL_ACTIVE = ft.TextStyle(size=12, weight=ft.FontWeight.W_700, color=TEXT)
STEP_NUMBER = ft.TextStyle(size=14, weight=ft.FontWeight.W_700, color=TEXT_INVERSE)
STEP_NUMBER_AHEAD = ft.TextStyle(
    size=14, weight=ft.FontWeight.W_700, color=TEXT_SECONDARY
)
HINT = ft.TextStyle(size=13, color=TEXT_SECONDARY)
EMPTY_TITLE = ft.TextStyle(size=16, weight=ft.FontWeight.W_700, color=TEXT)
EMPTY_BODY = ft.TextStyle(size=14, color=TEXT_SECONDARY)
DIALOG_TITLE = ft.TextStyle(size=20, weight=ft.FontWeight.W_700, color=TEXT)
DIALOG_BODY = ft.TextStyle(size=15, color=TEXT_SECONDARY)
REPORT_CELL = ft.TextStyle(size=14, color=TEXT)
REPORT_HEADER = ft.TextStyle(size=12, weight=ft.FontWeight.W_600, color=TEXT_SECONDARY)


def label(
    value: str, style: ft.TextStyle, color: str | None = None, *, nowrap: bool = False
) -> ft.Text:
    """A line of text in one of the roles above, optionally in another ink.

    `nowrap` keeps a table cell on one line; the cell's own width decides how much
    of the text is shown, so a narrow column can never push a row taller.
    """
    styled = style if color is None else dataclasses.replace(style, color=color)
    if nowrap:
        return ft.Text(
            value, style=styled, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS
        )
    return ft.Text(value, style=styled)


def hairline() -> ft.Border:
    """The card outline and the rule between table rows."""
    return ft.Border.all(1, BORDER_SUBTLE)


def field_border() -> ft.Border:
    """The outline a field and a chip show at rest."""
    return ft.Border.all(1, BORDER_STRONG)


def card_shadow() -> list[ft.BoxShadow]:
    """A card is lifted by a hairline and a very soft shadow together."""
    return [
        ft.BoxShadow(
            blur_radius=2,
            offset=ft.Offset(0, 1),
            color=ft.Colors.with_opacity(0.05, "#101828"),
        ),
        ft.BoxShadow(
            blur_radius=1,
            offset=ft.Offset(0, 1),
            color=ft.Colors.with_opacity(0.03, "#101828"),
        ),
    ]


def sheet_shadow() -> list[ft.BoxShadow]:
    """The footer casts its shadow upwards, over the content it covers."""
    return [
        ft.BoxShadow(
            blur_radius=16,
            offset=ft.Offset(0, -4),
            color=ft.Colors.with_opacity(0.06, "#101828"),
        )
    ]
