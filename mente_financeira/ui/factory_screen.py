"""Tela do simulador "Minha fábrica": comprar, alugar ou financiar uma máquina.

O jogador lê a proposta, escolhe um dos três caminhos e só então vê o VPL e o
caixa de cada um, com a explicação da melhor escolha. Depois pode mexer na TMA
e nos juros do banco ("E se…?") e ver a melhor escolha mudar.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Any

import flet as ft

from mente_financeira.core.factory import (
    CHOICES,
    EMOJIS,
    MACHINES,
    TITLES,
    Choice,
    Machine,
    Plan,
    best_choice,
    signed_money,
    simulate,
    verdict,
)
from mente_financeira.finance import percent
from mente_financeira.ui import style as s
from mente_financeira.ui.layout import Layout, layout_for
from mente_financeira.ui.sounds import SoundEffects

COLORS = {Choice.BUY: s.YELLOW, Choice.RENT: s.CYAN, Choice.FINANCE: s.PINK}
CHART_HEIGHT = 190
RATE_MAX = 30  # as barras de "E se…?" vão de 0% a 30% ao ano


class FactoryScreen:
    def __init__(
        self,
        page: ft.Page,
        *,
        on_home: Callable[[], None],
        sounds: SoundEffects | None = None,
        start: int = 0,
    ) -> None:
        self.page = page
        self.on_home = on_home
        self.sounds = sounds
        self.layout = layout_for(page.width)
        self.index = start % len(MACHINES)
        self.picked: Choice | None = None
        self.right = 0  # acertos e máquinas jogadas, só nesta visita
        self.played = 0
        self._reset_rates()
        # Partes que mudam quando o jogador mexe nas taxas (o resto fica parado).
        self.options_box = ft.Container()
        self.verdict_box = ft.Container()
        self.chart_box = ft.Container()
        self.tma_text = ft.Text()
        self.loan_text = ft.Text()

    # ------------------------------------------------------------ ciclo
    @property
    def machine(self) -> Machine:
        return MACHINES[self.index]

    @property
    def compact(self) -> bool:
        return self.layout is Layout.COMPACT

    @property
    def plans(self) -> dict[Choice, Plan]:
        return simulate(self.machine, tma=self.tma, loan_rate=self.loan_rate)

    def show(self) -> None:
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.bgcolor = s.BG_TOP
        self.page.controls.clear()
        self.page.add(self.build())
        self.page.update()

    def stop(self) -> None:
        pass  # nada roda em segundo plano

    def on_resize(self, event: Any) -> None:
        new_layout = layout_for(getattr(event, "width", None) or self.page.width)
        if new_layout is not self.layout:
            self.layout = new_layout
            self.show()

    def _reset_rates(self) -> None:
        self.tma = self.machine.tma
        self.loan_rate = self.machine.loan_rate

    # ------------------------------------------------------------ desenho
    def build(self) -> ft.Control:
        width = self.page.width or 1280
        content_width = None if self.compact else min(980, width - 64)
        items: list[ft.Control] = [self._header(), self._machine_card()]
        self._refresh_results()
        items.append(self.options_box)
        if self.picked is not None:
            items += [self.verdict_box, self._chart_panel(), self._what_if(), self._actions()]
        return ft.SafeArea(
            expand=True,
            content=ft.Container(
                expand=True,
                gradient=s.background(),
                content=ft.Stack(
                    [
                        # Posicionado nas quatro bordas: ocupa a tela toda e rola por inteiro.
                        ft.Container(
                            left=0,
                            top=0,
                            right=0,
                            bottom=0,
                            content=ft.Column(
                                [
                                    ft.Container(
                                        width=content_width,
                                        padding=ft.Padding.only(left=12, right=12, top=8, bottom=24)
                                        if self.compact
                                        else ft.Padding.symmetric(horizontal=0, vertical=16),
                                        content=ft.Column(
                                            items, spacing=14, horizontal_alignment=ft.CrossAxisAlignment.STRETCH
                                        ),
                                    )
                                ],
                                scroll=ft.ScrollMode.AUTO,
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                        )
                    ],
                    expand=True,
                ),
            ),
        )

    def _header(self) -> ft.Control:
        back = ft.TextButton(
            "Engenharia",
            icon=ft.Icons.ARROW_BACK_ROUNDED,
            on_click=lambda _: self.on_home(),
            style=ft.ButtonStyle(
                color=s.CYAN,
                icon_size=26 if self.compact else 30,
                text_style=ft.TextStyle(size=18 if self.compact else 22, weight=ft.FontWeight.W_900),
            ),
        )
        title = ft.Text(
            "🏭 Minha fábrica",
            size=22 if self.compact else 32,
            weight=ft.FontWeight.W_900,
            color=s.WHITE,
            text_align=ft.TextAlign.CENTER,
        )
        score = s.chip(f"Acertos: {self.right} de {self.played}", icon=ft.Icons.EMOJI_EVENTS_ROUNDED, color=s.GREEN)
        if self.compact:
            return ft.Column(
                [ft.Row([back, score], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), title],
                spacing=4,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            )
        return ft.Row(
            [ft.Container(back, expand=1), title, ft.Container(ft.Row([score], alignment=ft.MainAxisAlignment.END), expand=1)],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def _machine_card(self) -> ft.Control:
        m = self.machine
        story = ft.Text(
            spans=[
                ft.TextSpan("Sua fábrica precisa de "),
                ft.TextSpan(m.name, ft.TextStyle(weight=ft.FontWeight.W_900, color=s.YELLOW)),
                ft.TextSpan(f", que {m.use}. Ela aumenta o lucro em "),
                ft.TextSpan(f"{signed_money(Decimal(m.gain))} por ano", ft.TextStyle(weight=ft.FontWeight.W_900, color=s.GREEN)),
                ft.TextSpan(f" durante {m.years} anos. Qual caminho dá mais dinheiro?"),
            ],
            size=15 if self.compact else 18,
            color=s.WHITE,
        )
        chips = ft.Row(
            [
                s.chip(f"Caixa hoje: {signed_money(Decimal(m.cash))}", icon=ft.Icons.ACCOUNT_BALANCE_WALLET_ROUNDED, color=s.GREEN),
                s.chip(f"TMA: {percent(m.tma, 0)} ao ano", icon=ft.Icons.TRENDING_UP_ROUNDED, color=s.CYAN),
                s.chip(f"Máquina {self.index + 1} de {len(MACHINES)}", color="#8F88FF"),
            ],
            wrap=True,
            spacing=8,
            run_spacing=8,
        )
        tip = ft.Text(
            "TMA é quanto o dinheiro da fábrica renderia em outro lugar. "
            "O VPL traz cada ano para hoje com ela: VPL positivo quer dizer que vale a pena.",
            size=12,
            color=s.MUTED,
        )
        return s.glass(
            ft.Row(
                [
                    ft.Container(
                        width=64 if self.compact else 84,
                        height=64 if self.compact else 84,
                        border_radius=42,
                        alignment=ft.Alignment.CENTER,
                        bgcolor=ft.Colors.with_opacity(0.15, s.YELLOW),
                        content=ft.Text(m.emoji, size=34 if self.compact else 46),
                    ),
                    ft.Column([story, chips, tip], spacing=10, expand=True),
                ],
                spacing=14,
                vertical_alignment=ft.CrossAxisAlignment.START,
            ),
            padding=14 if self.compact else 20,
        )

    def _deal_lines(self, choice: Choice, plan: Plan) -> list[str]:
        m = self.machine
        if choice is Choice.BUY:
            return [f"Paga {signed_money(Decimal(m.price))} hoje.", f"No fim, revende por {signed_money(Decimal(m.resale))}."]
        if choice is Choice.RENT:
            return [f"Paga {signed_money(plan.payment)} por ano, com manutenção.", "Sem entrada; devolve a máquina no fim."]
        return [
            f"Entrada de {signed_money(m.down_payment)} hoje.",
            f"{m.years} parcelas de {signed_money(plan.payment)} por ano (juros de {percent(self.loan_rate, 0)} ao ano).",
            f"No fim, revende por {signed_money(Decimal(m.resale))}.",
        ]

    def _option_card(self, choice: Choice, plan: Plan, best: Choice) -> ft.Container:
        color = COLORS[choice]
        lines = [ft.Text(line, size=13, color=s.WHITE) for line in self._deal_lines(choice, plan)]
        body: list[ft.Control] = [
            ft.Row(
                [
                    ft.Text(EMOJIS[choice], size=26),
                    ft.Text(TITLES[choice], size=19, weight=ft.FontWeight.W_900, color=color, expand=True),
                ],
                spacing=8,
            ),
            *lines,
        ]
        picked = self.picked is choice
        if self.picked is None:
            body.append(
                ft.Container(
                    margin=ft.Margin.only(top=6),
                    padding=ft.Padding.symmetric(vertical=10),
                    border_radius=999,
                    alignment=ft.Alignment.CENTER,
                    bgcolor=ft.Colors.with_opacity(0.25, color),
                    border=ft.Border.all(1.5, color),
                    content=ft.Text("Escolher", size=16, weight=ft.FontWeight.W_900, color=s.WHITE),
                )
            )
        else:
            badges: list[ft.Control] = []
            if choice is best:
                badges.append(s.chip("Melhor escolha", icon=ft.Icons.STAR_ROUNDED, color=s.GREEN))
            if picked:
                badges.append(s.chip("Sua escolha", icon=ft.Icons.TOUCH_APP_ROUNDED, color=color))
            if not plan.fits:
                badges.append(s.chip("Falta caixa", icon=ft.Icons.WARNING_ROUNDED, color=s.ORANGE))
            body += [
                ft.Divider(height=8, color=s.GLASS_BORDER),
                ft.Text("VPL", size=12, color=s.MUTED),
                ft.Text(
                    signed_money(plan.npv),
                    size=26,
                    weight=ft.FontWeight.W_900,
                    color=s.GREEN if plan.npv >= 0 else s.ORANGE,
                ),
                ft.Text(
                    f"Caixa mais baixo: {signed_money(plan.lowest)} (ano {plan.lowest_year})",
                    size=13,
                    weight=ft.FontWeight.BOLD,
                    color=s.WHITE if plan.fits else s.ORANGE,
                ),
                ft.Row(badges, wrap=True, spacing=6, run_spacing=6),
            ]
        return ft.Container(
            data=choice,
            on_click=self._pick if self.picked is None else None,
            ink=self.picked is None,
            expand=not self.compact,
            padding=14,
            border_radius=22,
            bgcolor=ft.Colors.with_opacity(0.20 if picked else 0.08, color if picked else s.WHITE),
            border=ft.Border.all(2.5 if picked or (self.picked is not None and choice is best) else 1, color if picked else (s.GREEN if self.picked is not None and choice is best else s.GLASS_BORDER)),
            content=ft.Column(body, spacing=6),
        )

    def _refresh_results(self) -> None:
        """Remonta o que depende das taxas: cartões, explicação e gráfico."""

        plans = self.plans
        best = best_choice(plans)
        cards = [self._option_card(choice, plans[choice], best) for choice in CHOICES]
        self.options_box.content = (
            ft.Column(cards, spacing=10)
            if self.compact
            else ft.Row(cards, spacing=12, vertical_alignment=ft.CrossAxisAlignment.START)
        )
        if self.picked is None:
            return
        right = self.picked is best
        self.verdict_box.content = ft.Container(
            padding=14,
            border_radius=20,
            bgcolor=ft.Colors.with_opacity(0.18, s.GREEN if right else s.ORANGE),
            border=ft.Border.all(1.5, s.GREEN if right else s.ORANGE),
            content=ft.Row(
                [
                    ft.Text("🎉" if right else "🤔", size=30),
                    ft.Text(
                        verdict(self.machine, plans, self.picked, tma=self.tma, loan_rate=self.loan_rate),
                        size=15,
                        color=s.WHITE,
                        expand=True,
                    ),
                ],
                spacing=12,
            ),
        )
        self.chart_box.content = self._chart(plans)
        self.tma_text.value = f"TMA da fábrica: {percent(self.tma, 0)} ao ano"
        self.loan_text.value = f"Juros do banco: {percent(self.loan_rate, 0)} ao ano"

    # ------------------------------------------------------------ gráfico
    def _chart_panel(self) -> ft.Control:
        legend = ft.Row(
            [
                ft.Row(
                    [
                        ft.Container(width=12, height=12, border_radius=3, bgcolor=COLORS[choice]),
                        ft.Text(TITLES[choice], size=12, color=s.WHITE),
                    ],
                    spacing=6,
                    tight=True,
                )
                for choice in CHOICES
            ],
            wrap=True,
            spacing=14,
        )
        return s.glass(
            ft.Column(
                [
                    ft.Text("Caixa da fábrica ano a ano", size=18, weight=ft.FontWeight.W_900, color=s.WHITE),
                    ft.Text(
                        "Quanto sobra no caixa no fim de cada ano. Barra para baixo do zero: faltou dinheiro.",
                        size=12,
                        color=s.MUTED,
                    ),
                    legend,
                    self.chart_box,
                ],
                spacing=8,
            ),
            padding=14 if self.compact else 20,
        )

    def _chart(self, plans: dict[Choice, Plan]) -> ft.Control:
        values = [value for plan in plans.values() for value in plan.balances]
        top, bottom = max(max(values), Decimal(0)), min(min(values), Decimal(0))
        span = (top - bottom) or Decimal(1)
        zero = float(CHART_HEIGHT * top / span)  # distância do topo até a linha do zero

        def bar(choice: Choice, year: int, value: Decimal, left: float, width: float) -> ft.Container:
            height = max(2.0, float(CHART_HEIGHT * abs(value) / span))
            return ft.Container(
                left=left,
                top=zero - height if value >= 0 else zero,
                width=width,
                height=height,
                border_radius=ft.BorderRadius.only(top_left=4, top_right=4) if value >= 0 else ft.BorderRadius.only(bottom_left=4, bottom_right=4),
                bgcolor=COLORS[choice] if value >= 0 else s.ORANGE,
                opacity=1 if choice is self.picked else 0.75,
                tooltip=f"{TITLES[choice]}, ano {year}: {signed_money(value)}",
            )

        years = len(plans[Choice.BUY].balances)
        axis_width = 78 if self.compact else 96
        available = (self.page.width or 1280) - (24 + 28 if self.compact else 64 + 40)
        group = max(36.0, (min(available, 980 - 40) - axis_width) / years)
        bar_width = min(26.0, (group - 10) / 3)
        first = (group - 3 * bar_width - 4) / 2  # barras centradas sobre o "Ano t"
        groups = []
        for year in range(years):
            bars = [
                bar(choice, year, plans[choice].balances[year], first + index * (bar_width + 2), bar_width)
                for index, choice in enumerate(CHOICES)
            ]
            groups.append(
                ft.Column(
                    [
                        ft.Stack(
                            [ft.Container(left=0, right=0, top=zero, height=1, bgcolor=s.MUTED), *bars],
                            width=group,
                            height=CHART_HEIGHT,
                        ),
                        ft.Text(f"Ano {year}", size=11, color=s.MUTED, width=group, text_align=ft.TextAlign.CENTER),
                    ],
                    spacing=4,
                )
            )
        labels = [(0.0, top), (zero, Decimal(0))]
        if bottom < 0:
            labels.append((CHART_HEIGHT, bottom))
        axis = ft.Stack(
            [
                ft.Container(
                    left=0,
                    top=min(max(0.0, y - 8), CHART_HEIGHT - 14),
                    width=axis_width - 6,
                    content=ft.Text(signed_money(value), size=10, color=s.MUTED, text_align=ft.TextAlign.RIGHT),
                )
                for y, value in labels
                if y == 0 or abs(y - zero) > 16 or value == 0
            ],
            width=axis_width,
            height=CHART_HEIGHT,
        )
        return ft.Row([axis, *groups], spacing=0, vertical_alignment=ft.CrossAxisAlignment.START)

    # ------------------------------------------------------------ E se…?
    def _what_if(self) -> ft.Control:
        def slider(value: Decimal, color: str, on_change: Callable[[Any], None]) -> ft.Slider:
            return ft.Slider(
                min=0,
                max=RATE_MAX,
                divisions=RATE_MAX,
                round=0,
                value=float(value * 100),
                label="{value}%",
                active_color=color,
                on_change=on_change,
            )

        for text in (self.tma_text, self.loan_text):
            text.size, text.weight, text.color = 14, ft.FontWeight.BOLD, s.WHITE
        return s.glass(
            ft.Column(
                [
                    ft.Text("E se…?", size=18, weight=ft.FontWeight.W_900, color=s.WHITE),
                    ft.Text(
                        "Mude as taxas e veja o VPL, o caixa e a melhor escolha mudarem.",
                        size=12,
                        color=s.MUTED,
                    ),
                    self.tma_text,
                    slider(self.tma, s.CYAN, self._change_tma),
                    self.loan_text,
                    slider(self.loan_rate, s.PINK, self._change_loan),
                    ft.TextButton(
                        "Voltar às taxas da máquina",
                        icon=ft.Icons.RESTART_ALT_ROUNDED,
                        on_click=self._restore_rates,
                        style=ft.ButtonStyle(color=s.CYAN),
                    ),
                ],
                spacing=6,
            ),
            padding=14 if self.compact else 20,
        )

    def _actions(self) -> ft.Control:
        return ft.Column(
            [
                s.pill_button("PRÓXIMA MÁQUINA", ft.Icons.ARROW_FORWARD_ROUNDED, self._next, height=56),
                ft.Text(
                    "Conta simplificada: ganhos, aluguéis e parcelas no fim de cada ano; "
                    "financiamento pela Tabela Price; o caixa parado não rende.",
                    size=11,
                    color=s.MUTED,
                    text_align=ft.TextAlign.CENTER,
                ),
            ],
            spacing=8,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

    # ------------------------------------------------------------ ações
    def _pick(self, event: Any) -> None:
        choice = event.control.data
        if self.picked is not None or choice not in CHOICES:
            return
        self.picked = Choice(choice)
        right = self.picked is best_choice(self.plans)
        self.played += 1
        self.right += right
        if self.sounds is not None:
            self.sounds.play("incentivo" if right else "erro")
        self.show()

    def _change_rates(self) -> None:
        self._refresh_results()
        self.page.update()

    def _change_tma(self, event: Any) -> None:
        self.tma = Decimal(round(float(event.control.value))) / 100
        self._change_rates()

    def _change_loan(self, event: Any) -> None:
        self.loan_rate = Decimal(round(float(event.control.value))) / 100
        self._change_rates()

    def _restore_rates(self, _: Any = None) -> None:
        self._reset_rates()
        self.show()  # as barras voltam para as taxas da máquina

    def _next(self, _: Any = None) -> None:
        self.index = (self.index + 1) % len(MACHINES)
        self.picked = None
        self._reset_rates()
        self.show()
