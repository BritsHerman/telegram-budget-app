import io

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd

from src.helpers import get_budget_period


def generate_budget_chart(user_id: str, budget_day: int) -> io.BytesIO:
    """Return a JPEG chart of spending vs budget as an in-memory buffer."""
    from src.db.transactions import get_expense_transactions_for_period
    from src.db.budgets import get_expense_budgets

    start, end = get_budget_period(budget_day)

    transactions = get_expense_transactions_for_period(user_id, start, end)
    budgets = get_expense_budgets(user_id)

    if transactions:
        tx_rows = [{"category": t["categories"]["name"], "amount": float(t["amount"])}
                   for t in transactions]
        spent_df = (
            pd.DataFrame(tx_rows)
            .groupby("category")["amount"]
            .sum()
            .reset_index()
            .rename(columns={"amount": "spent"})
        )
    else:
        spent_df = pd.DataFrame(columns=["category", "spent"])

    if budgets:
        budget_rows = [{"category": b["categories"]["name"], "amount": float(b["amount"])}
                       for b in budgets]
        budget_df = pd.DataFrame(budget_rows)
    else:
        budget_df = pd.DataFrame(columns=["category", "amount"])

    combined = pd.merge(budget_df, spent_df, on="category", how="outer").fillna(0)
    combined["remaining"] = (combined["amount"] - combined["spent"]).clip(lower=0)

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(combined["category"], combined["spent"], label="Spent", color="orangered")
    ax.bar(combined["category"], combined["remaining"],
           bottom=combined["spent"], label="Remaining", color="royalblue")

    for idx, row in combined.iterrows():
        if row["spent"] > 0:
            ax.text(idx, row["spent"] / 2, f'R{row["spent"]:.0f}',
                    ha='center', va='center', color="white", fontsize=8)
        if row["remaining"] > 0:
            ax.text(idx, row["spent"] + row["remaining"] / 2, f'R{row["remaining"]:.0f}',
                    ha='center', va='center', color="white", fontsize=8)

    ax.set_title(
        f"Spending vs Budget  ({start.strftime('%d %b')} – {end.strftime('%d %b')})",
        fontsize=14,
    )
    ax.set_ylabel("Amount (R)")
    plt.xticks(rotation=45, ha='right')
    plt.legend()
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='jpeg', dpi=200)
    plt.close(fig)
    buf.seek(0)
    return buf
