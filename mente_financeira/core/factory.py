"""Simulador "Minha fábrica" (trilha de Engenharia de Produção).

A fábrica precisa de uma máquina e tem três caminhos: comprar à vista, alugar
ou financiar. Para cada um o simulador monta o fluxo de caixa ano a ano, o VPL
com a TMA da fábrica e o saldo do caixa. A melhor escolha é a de maior VPL
entre as que o caixa aguenta (o saldo nunca fica negativo).

Simplificações, ditas também na tela: ganhos, aluguéis e parcelas caem no fim
de cada ano; o financiamento é pela Tabela Price, no mesmo prazo de uso da
máquina; o dinheiro parado no caixa não rende.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from mente_financeira.finance import decimal, net_present_value, percent, price_payment, round_money


class Choice(StrEnum):
    BUY = "comprar"
    RENT = "alugar"
    FINANCE = "financiar"


CHOICES = (Choice.BUY, Choice.RENT, Choice.FINANCE)
TITLES = {Choice.BUY: "Comprar à vista", Choice.RENT: "Alugar", Choice.FINANCE: "Financiar"}
EMOJIS = {Choice.BUY: "💵", Choice.RENT: "🔑", Choice.FINANCE: "🏦"}


@dataclass(frozen=True, slots=True)
class Machine:
    key: str
    emoji: str
    name: str  # "um robô de solda"
    use: str  # o que a máquina faz pela fábrica
    price: int
    gain: int  # aumento do lucro por ano
    years: int  # anos de uso
    resale: int  # quanto ainda vale no fim (para quem comprou ou financiou)
    rent: int  # aluguel por ano, com manutenção
    down: Decimal  # entrada do financiamento (fração do preço)
    loan_rate: Decimal  # juros do banco ao ano
    cash: int  # dinheiro em caixa hoje
    tma: Decimal  # taxa mínima de atratividade: quanto o dinheiro renderia em outro lugar

    @property
    def down_payment(self) -> Decimal:
        return round_money(self.price * self.down)


# Cada máquina ensina uma coisa: a ordem alterna a resposta certa.
MACHINES: tuple[Machine, ...] = (
    Machine(
        "embaladora",
        "📦",
        "uma máquina de embalar",
        "embala os produtos duas vezes mais rápido",
        price=60_000,
        gain=18_000,
        years=5,
        resale=10_000,
        rent=15_000,
        down=Decimal("0.20"),
        loan_rate=Decimal("0.12"),
        cash=80_000,
        tma=Decimal("0.10"),
    ),
    Machine(
        "robo_solda",
        "🤖",
        "um robô de solda",
        "solda as peças sem parar e quase sem erro",
        price=150_000,
        gain=45_000,
        years=5,
        resale=30_000,
        rent=36_000,
        down=Decimal("0.20"),
        loan_rate=Decimal("0.08"),
        cash=60_000,
        tma=Decimal("0.12"),
    ),
    Machine(
        "caminhao",
        "🚚",
        "um caminhão de entregas",
        "leva os pedidos da fábrica até os clientes",
        price=200_000,
        gain=50_000,
        years=4,
        resale=40_000,
        rent=30_000,
        down=Decimal("0.30"),
        loan_rate=Decimal("0.14"),
        cash=250_000,
        tma=Decimal("0.12"),
    ),
    Machine(
        "costura",
        "🧵",
        "uma máquina de costura industrial",
        "costura uniformes para novos clientes",
        price=40_000,
        gain=14_000,
        years=4,
        resale=8_000,
        rent=12_500,
        down=Decimal("0.20"),
        loan_rate=Decimal("0.09"),
        cash=60_000,
        tma=Decimal("0.16"),
    ),
)


@dataclass(frozen=True, slots=True)
class Plan:
    choice: Choice
    flows: tuple[Decimal, ...]  # ano 0, 1, …, N (entradas positivas, saídas negativas)
    payment: Decimal  # parcela ou aluguel por ano (zero para quem compra)
    npv: Decimal
    balances: tuple[Decimal, ...]  # caixa no fim de cada ano, a partir do ano 0

    @property
    def lowest(self) -> Decimal:
        return min(self.balances)

    @property
    def fits(self) -> bool:
        """O caixa aguenta: o saldo nunca fica negativo."""

        return self.lowest >= 0

    @property
    def lowest_year(self) -> int:
        return self.balances.index(self.lowest)


def _plan(machine: Machine, choice: Choice, tma: Decimal, loan_rate: Decimal) -> Plan:
    years = machine.years
    if choice is Choice.BUY:
        payment = Decimal(0)
        start = Decimal(-machine.price)
    elif choice is Choice.RENT:
        payment = Decimal(machine.rent)
        start = Decimal(0)
    else:
        payment = round_money(price_payment(machine.price - machine.down_payment, loan_rate, years))
        start = -machine.down_payment
    flows = [start, *(Decimal(machine.gain) - payment for _ in range(years))]
    if choice is not Choice.RENT:
        flows[-1] += machine.resale  # a máquina é da fábrica: revende no fim
    npv = round_money(net_present_value(-flows[0], flows[1:], tma))
    balances: list[Decimal] = []
    cash = Decimal(machine.cash)
    for flow in flows:
        cash += flow
        balances.append(cash)
    return Plan(choice, tuple(flows), payment, npv, tuple(balances))


def simulate(machine: Machine, *, tma: Decimal | None = None, loan_rate: Decimal | None = None) -> dict[Choice, Plan]:
    """Os três caminhos para a máquina; ``tma`` e ``loan_rate`` trocam as taxas ("E se…?")."""

    tma = machine.tma if tma is None else decimal(tma)
    loan_rate = machine.loan_rate if loan_rate is None else decimal(loan_rate)
    return {choice: _plan(machine, choice, tma, loan_rate) for choice in CHOICES}


def best_choice(plans: Mapping[Choice, Plan]) -> Choice:
    """Maior VPL entre as escolhas que o caixa aguenta (se nenhuma aguenta, o maior VPL)."""

    candidates = [plan for plan in plans.values() if plan.fits] or list(plans.values())
    return max(candidates, key=lambda plan: plan.npv).choice


def signed_money(value: Decimal) -> str:
    """R$ sem centavos e com sinal de menos de verdade: −R$ 12.000."""

    whole = f"{abs(round_money(value)):,.0f}".replace(",", ".")
    return f"−R$ {whole}" if value < 0 else f"R$ {whole}"


def verdict(machine: Machine, plans: Mapping[Choice, Plan], picked: Choice, *, tma: Decimal, loan_rate: Decimal) -> str:
    """Explica o resultado da escolha do jogador, comparando com a melhor."""

    best = best_choice(plans)
    mine, top = plans[picked], plans[best]
    if picked is best:
        text = f"Boa escolha! {TITLES[best]} tem o maior VPL ({signed_money(top.npv)}) e o caixa aguenta."
    elif not mine.fits:
        text = (
            f"Faltaria dinheiro: com essa escolha o caixa chega a {signed_money(mine.lowest)} "
            f"no ano {mine.lowest_year}. A melhor era {TITLES[best].lower()} (VPL {signed_money(top.npv)})."
        )
    else:
        text = (
            f"Dá para pagar, mas {TITLES[best].lower()} vale {signed_money(top.npv - mine.npv)} a mais "
            f"em VPL ({signed_money(top.npv)} contra {signed_money(mine.npv)})."
        )
    return f"{text} {lesson(machine, plans, tma=tma, loan_rate=loan_rate)}"


def lesson(machine: Machine, plans: Mapping[Choice, Plan], *, tma: Decimal, loan_rate: Decimal) -> str:
    """A ideia por trás da melhor escolha, em uma frase."""

    best = best_choice(plans)
    if best is Choice.RENT:
        if plans[Choice.BUY].npv < 0:
            return "Comprar tem VPL negativo: a máquina não se paga. Alugar só cobra pelo uso."
        return "O aluguel é barato perto do ganho: sem entrada e sem juros, sobra mais."
    if best is Choice.FINANCE:
        if not plans[Choice.BUY].fits:
            return "O caixa não paga a máquina à vista: financiar divide o preço em parcelas."
        if loan_rate < tma:
            return (
                f"Os juros do banco ({percent(loan_rate, 0)}) são menores que a TMA ({percent(tma, 0)}): "
                "vale guardar o dinheiro e pagar aos poucos."
            )
        return "Financiar pede pouco dinheiro hoje e a máquina fica para a fábrica."
    if loan_rate > tma:
        return (
            f"Os juros do banco ({percent(loan_rate, 0)}) são maiores que a TMA ({percent(tma, 0)}): "
            "se o caixa tem o dinheiro, pagar à vista sai mais barato."
        )
    return "Comprando, a fábrica não paga juros nem aluguel e ainda revende a máquina no fim."
