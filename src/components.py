"""The design's component library: the pieces every step is built from.

A screen composes cards and tables; it never styles a raw control. Keeping the
look here means the four steps cannot drift apart, and the whole app can be
restyled by editing this file and `theme`.
"""

import flet as ft

import theme as t


def icon_tile(
    icon: ft.IconData, colors: tuple[str, str], *, size: int = 24
) -> ft.Container:
    """A pastel circle carrying a commodity's or a section's glyph."""
    background, ink = colors
    return ft.Container(
        width=size,
        height=size,
        bgcolor=background,
        border_radius=t.RADIUS_PILL,
        alignment=ft.Alignment.CENTER,
        content=ft.Icon(icon, color=ink, size=round(size * 0.55)),
    )


def card(
    content: ft.Control, *, key: str | None = None, expand: bool = False
) -> ft.Container:
    """The only container in the app: white, rounded, hairline and soft shadow."""
    return ft.Container(
        key=key,
        expand=expand,
        bgcolor=t.SURFACE,
        border=t.hairline(),
        border_radius=t.RADIUS_CARD,
        shadow=t.card_shadow(),
        padding=t.SPACE_3,
        content=content,
    )


def section(
    icon: ft.IconData,
    colors: tuple[str, str],
    title: str,
    content: ft.Control,
    *,
    key: str | None = None,
    expand: bool = False,
) -> ft.Container:
    """A card whose first line names the section.

    `expand` lets a section fill the screen and hand the spare height to its content,
    which is how the report gives the table a viewport of its own.
    """
    return card(
        ft.Column(
            expand=expand,
            spacing=t.SPACE_3,
            controls=[
                ft.Row(
                    spacing=t.SPACE_2,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        icon_tile(icon, colors, size=34),
                        ft.Text(title, style=t.CARD_TITLE, expand=True),
                    ],
                ),
                content,
            ],
        ),
        key=key,
        expand=expand,
    )


def cell(
    content: ft.Control | None,
    *,
    flex: int = 1,
    align: ft.Alignment | None = ft.Alignment.CENTER_RIGHT,
    bgcolor: str | None = None,
    padding: tuple[int, int] = (6, 6),
) -> ft.Container:
    """One table cell: a fixed share of the row, padded and aligned.

    `align=None` stretches the content across the cell, which is what a row of
    several pieces needs; a plain value is aligned inside the cell instead.
    """
    return ft.Container(
        expand=flex,
        bgcolor=bgcolor,
        alignment=align,
        padding=ft.Padding.symmetric(horizontal=padding[0], vertical=padding[1]),
        content=content,
    )


def row(
    cells: list[ft.Control], *, bgcolor: str | None = None, rule: bool = True
) -> ft.Container:
    """One line of a table, separated from the line above by a hairline."""
    return ft.Container(
        bgcolor=bgcolor or t.SURFACE,
        border=ft.Border(bottom=ft.BorderSide(1, t.BORDER_SUBTLE)) if rule else None,
        content=ft.Row(spacing=0, controls=cells),
    )


def number_field(
    value: object, *, key: str, on_change, flex: int = 1, disabled: bool = False
) -> ft.TextField:
    """A whole-number field: digits only, right-aligned, sized by its row.

    A disabled field is a closed day's count: tinted, borderless, and out of reach
    of the keyboard, but still showing the number the day keeps.
    """
    return ft.TextField(
        key=key,
        value=_whole_text(value),
        expand=flex,
        dense=True,
        max_lines=1,
        text_size=14,
        text_style=ft.TextStyle(
            size=14,
            weight=ft.FontWeight.W_500,
            color=t.TEXT_TERTIARY if disabled else t.TEXT,
        ),
        text_align=ft.TextAlign.RIGHT,
        keyboard_type=ft.KeyboardType.NUMBER,
        input_filter=ft.InputFilter(allow=True, regex_string=r"^\d*$"),
        border=None if disabled else _field_border(),
        filled=True,
        fill_color=t.CLOSED_FIELD if disabled else t.SURFACE,
        content_padding=ft.Padding.symmetric(horizontal=6, vertical=7),
        disabled=disabled,
        on_change=on_change,
    )


def _field_border() -> dict[ft.ControlState, ft.InputBorder]:
    """The outline a field wears at rest, and how it lights up when focused."""
    return {
        ft.ControlState.DEFAULT: ft.OutlineInputBorder(
            border_radius=t.RADIUS_FIELD, side=ft.BorderSide(1, t.BORDER_STRONG)
        ),
        ft.ControlState.FOCUSED: ft.OutlineInputBorder(
            border_radius=t.RADIUS_FIELD, side=ft.BorderSide(1.5, t.PRIMARY_500)
        ),
    }


def _whole_text(value: object) -> str:
    """A stored number as the field shows it: `0` rather than `0.0`."""
    if value is None:
        return ""
    return str(value).removesuffix(".0")


def button(
    text: str,
    *,
    key: str,
    on_click,
    icon: ft.IconData | None = None,
    variant: str = "filled",
    disabled: bool = False,
    expand: bool = False,
) -> ft.Control:
    """One of the design's four button variants, all pill-shaped and 52 dp tall."""
    style = _button_style(variant)
    if variant == "outlined":
        return ft.OutlinedButton(
            key=key,
            content=text,
            icon=icon,
            style=style,
            disabled=disabled,
            expand=expand,
            on_click=on_click,
        )
    return ft.FilledButton(
        key=key,
        content=text,
        icon=icon,
        style=style,
        disabled=disabled,
        expand=expand,
        on_click=on_click,
    )


def _button_style(variant: str) -> ft.ButtonStyle:
    """The fill, ink and border a button variant wears."""
    fill: str | None
    ink: str = t.TEXT_INVERSE
    side: ft.BorderSide | None = None
    if variant == "outlined":
        fill, ink, side = None, t.PRIMARY_600, ft.BorderSide(1.5, t.PRIMARY_600)
    elif variant == "tinted":
        fill, ink = t.PRIMARY_100, t.PRIMARY_600
    elif variant == "text":
        fill, ink = None, t.PRIMARY_600
    elif variant == "destructive":
        fill = t.DANGER
    else:
        fill = t.PRIMARY_600
    return ft.ButtonStyle(
        bgcolor=fill,
        color=ink,
        side=side,
        elevation=0,
        padding=ft.Padding.symmetric(horizontal=16, vertical=10),
        shape=ft.RoundedRectangleBorder(radius=t.RADIUS_PILL),
        text_style=t.BUTTON,
        icon_size=18,
    )


def empty_state(icon: ft.IconData, title: str, body: str) -> ft.Container:
    """The one place in the app that carries an illustration."""
    return ft.Container(
        bgcolor=t.PRIMARY_050,
        border=t.field_border(),
        border_radius=t.RADIUS_CARD,
        padding=t.SPACE_4,
        alignment=ft.Alignment.CENTER,
        content=ft.Column(
            spacing=t.SPACE_2,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Icon(
                    icon, size=30, color=ft.Colors.with_opacity(0.7, t.PRIMARY_600)
                ),
                t.label(title, t.EMPTY_TITLE),
                t.label(body, t.EMPTY_BODY),
            ],
        ),
    )


def banner(
    icon: ft.IconData, title: str, body: str, *, ink: str = t.DANGER
) -> ft.Container:
    """A problem inside a card that the user can read and act on."""
    return ft.Container(
        bgcolor=ft.Colors.with_opacity(0.08, ink),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.3, ink)),
        border_radius=t.RADIUS_FIELD,
        padding=t.SPACE_3,
        content=ft.Row(
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.START,
            controls=[
                ft.Icon(icon, size=20, color=ink),
                ft.Column(
                    spacing=2,
                    expand=True,
                    controls=[
                        t.label(title, t.EMPTY_TITLE),
                        t.label(body, t.EMPTY_BODY),
                    ],
                ),
            ],
        ),
    )
