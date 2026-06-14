import io

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pandas as pd

from src.helpers import get_budget_period


def generate_summary_charts(user_id: str, budget_day: int) -> list[tuple[io.BytesIO, str]]:
    """Return a list of (jpeg_buffer, caption) for each chart."""
    from src.db.transactions import (
        get_expense_transactions_for_period,
        get_income_transactions_for_period,
    )
    from src.db.budgets import get_expense_budgets

    start, end = get_budget_period(budget_day)
    period_str = f"{start.strftime('%d %b')} – {end.strftime('%d %b')}"

    expense_txns = get_expense_transactions_for_period(user_id, start, end)
    income_txns  = get_income_transactions_for_period(user_id, start, end)
    budgets      = get_expense_budgets(user_id)

    charts = []
    charts.append(_budget_tracker(expense_txns, budgets, period_str))

    if len({t["categories"]["name"] for t in expense_txns}) > 1:
        charts.append(_spending_pie(expense_txns, period_str))

    charts.append(_net_position(expense_txns, income_txns, period_str))

    return charts


# ── Chart 1: Budget tracker ───────────────────────────────────────────────────

def _budget_tracker(expense_txns: list, budgets: list, period_str: str) -> tuple[io.BytesIO, str]:
    spent_by_cat: dict[str, float] = {}
    for t in expense_txns:
        name = t["categories"]["name"]
        spent_by_cat[name] = spent_by_cat.get(name, 0) + float(t["amount"])

    budget_by_cat = {b["categories"]["name"]: float(b["amount"]) for b in budgets}
    categories = sorted(set(list(spent_by_cat) + list(budget_by_cat)))

    rows = []
    for cat in categories:
        spent  = spent_by_cat.get(cat, 0)
        budget = budget_by_cat.get(cat, 0)
        rows.append({
            "category":  cat,
            "within":    min(spent, budget),
            "remaining": max(budget - spent, 0),
            "over":      max(spent - budget, 0),
        })

    if not rows:
        fig, ax = plt.subplots(figsize=(6, 3))
        ax.text(0.5, 0.5, "No expense data yet", ha="center", va="center", fontsize=14)
        ax.axis("off")
        return _buf(fig), "📊 Budget Tracker — no data yet"

    cats     = [r["category"] for r in rows]
    within   = [r["within"]    for r in rows]
    rem      = [r["remaining"] for r in rows]
    over     = [r["over"]      for r in rows]

    fig, ax = plt.subplots(figsize=(max(8, len(cats) * 1.4), 6))

    b1 = ax.bar(cats, within, color="#e05252", label="Spent")
    b2 = ax.bar(cats, rem,    bottom=within,         color="#4a90d9", label="Remaining")
    b3 = ax.bar(cats, over,   bottom=[w + r for w, r in zip(within, rem)], color="#b71c1c", label="Over budget")

    for i, r in enumerate(rows):
        if r["within"] > 0:
            ax.text(i, r["within"] / 2, f'R{r["within"]:.0f}',
                    ha="center", va="center", color="white", fontsize=8, fontweight="bold")
        if r["remaining"] > 0:
            ax.text(i, r["within"] + r["remaining"] / 2, f'R{r["remaining"]:.0f}',
                    ha="center", va="center", color="white", fontsize=8, fontweight="bold")
        if r["over"] > 0:
            ax.text(i, r["within"] + r["remaining"] + r["over"] / 2,
                    f'+R{r["over"]:.0f}', ha="center", va="center",
                    color="white", fontsize=8, fontweight="bold")

    ax.set_title(f"Budget Tracker  ·  {period_str}", fontsize=13, pad=12)
    ax.set_ylabel("Amount (R)")
    ax.legend(loc="upper right")
    plt.xticks(rotation=40, ha="right")
    plt.tight_layout()
    return _buf(fig), "📊 *Budget Tracker* — spent vs remaining per category. Dark red = over budget."


# ── Chart 2: Spending breakdown pie ──────────────────────────────────────────

def _spending_pie(expense_txns: list, period_str: str) -> tuple[io.BytesIO, str]:
    spent_by_cat: dict[str, float] = {}
    for t in expense_txns:
        name = t["categories"]["name"]
        spent_by_cat[name] = spent_by_cat.get(name, 0) + float(t["amount"])

    labels  = list(spent_by_cat.keys())
    amounts = [spent_by_cat[l] for l in labels]
    total   = sum(amounts)

    colours = plt.cm.Set2.colors  # type: ignore

    fig, ax = plt.subplots(figsize=(7, 7))
    wedges, texts, autotexts = ax.pie(
        amounts,
        labels=None,
        autopct=lambda p: f"R{p * total / 100:.0f}\n({p:.1f}%)",
        colors=colours[:len(labels)],
        startangle=140,
        pctdistance=0.75,
        wedgeprops={"linewidth": 1.5, "edgecolor": "white"},
    )
    for at in autotexts:
        at.set_fontsize(9)
        at.set_color("white")
        at.set_fontweight("bold")

    ax.legend(wedges, labels, loc="lower center", bbox_to_anchor=(0.5, -0.08),
              ncol=3, fontsize=9)
    ax.set_title(f"Where's Your Money Going?  ·  {period_str}", fontsize=13, pad=16)
    plt.tight_layout()
    return _buf(fig), f"🥧 *Spending Breakdown* — total expenses: R{total:.2f}"


# ── Chart 3: Net position ─────────────────────────────────────────────────────

def _net_position(expense_txns: list, income_txns: list, period_str: str) -> tuple[io.BytesIO, str]:
    total_income  = sum(float(t["amount"]) for t in income_txns)
    total_expense = sum(float(t["amount"]) for t in expense_txns)
    net           = total_income - total_expense

    income_by_cat:  dict[str, float] = {}
    expense_by_cat: dict[str, float] = {}
    for t in income_txns:
        n = t["categories"]["name"]
        income_by_cat[n]  = income_by_cat.get(n, 0)  + float(t["amount"])
    for t in expense_txns:
        n = t["categories"]["name"]
        expense_by_cat[n] = expense_by_cat.get(n, 0) + float(t["amount"])

    fig, axes = plt.subplots(1, 2, figsize=(12, 6))

    # Left: stacked income bar
    ax_inc = axes[0]
    colours_inc = plt.cm.Greens(  # type: ignore
        [0.4 + 0.5 * i / max(len(income_by_cat), 1) for i in range(len(income_by_cat))]
    )
    bottom = 0.0
    for (cat, amt), colour in zip(income_by_cat.items(), colours_inc):
        ax_inc.bar(["Income"], amt, bottom=bottom, color=colour)
        if amt > total_income * 0.05:
            ax_inc.text(0, bottom + amt / 2, f"{cat}\nR{amt:.0f}",
                        ha="center", va="center", fontsize=8, color="white", fontweight="bold")
        bottom += amt
    ax_inc.set_title("Total Income", fontsize=11)
    ax_inc.set_ylabel("Amount (R)")
    if total_income:
        ax_inc.text(0, total_income + total_income * 0.02, f"R{total_income:.2f}",
                    ha="center", fontsize=10, fontweight="bold", color="#2e7d32")

    # Right: stacked expense bar
    ax_exp = axes[1]
    colours_exp = plt.cm.Reds(  # type: ignore
        [0.4 + 0.5 * i / max(len(expense_by_cat), 1) for i in range(len(expense_by_cat))]
    )
    bottom = 0.0
    for (cat, amt), colour in zip(expense_by_cat.items(), colours_exp):
        ax_exp.bar(["Expenses"], amt, bottom=bottom, color=colour)
        if amt > total_expense * 0.05:
            ax_exp.text(0, bottom + amt / 2, f"{cat}\nR{amt:.0f}",
                        ha="center", va="center", fontsize=8, color="white", fontweight="bold")
        bottom += amt
    ax_exp.set_title("Total Expenses", fontsize=11)
    if total_expense:
        ax_exp.text(0, total_expense + total_expense * 0.02, f"R{total_expense:.2f}",
                    ha="center", fontsize=10, fontweight="bold", color="#c62828")

    net_colour = "#2e7d32" if net >= 0 else "#c62828"
    net_emoji  = "✅" if net >= 0 else "⚠️"
    fig.suptitle(
        f"Income vs Expenses  ·  {period_str}\n{net_emoji}  Net: R{net:+.2f}",
        fontsize=13, y=1.01, color=net_colour, fontweight="bold",
    )
    plt.tight_layout()
    caption = (
        f"💰 *Net Position*  R{net:+.2f}  "
        f"({'saving' if net >= 0 else 'overspending'} this period)"
    )
    return _buf(fig), caption


# ── helper ────────────────────────────────────────────────────────────────────

def _buf(fig) -> io.BytesIO:
    buf = io.BytesIO()
    fig.savefig(buf, format="jpeg", dpi=180, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf
