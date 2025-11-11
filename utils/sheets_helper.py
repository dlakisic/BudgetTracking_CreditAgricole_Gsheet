import pandas as pd
from typing import List, Dict
import re


def process_transactions(transactions: List[Dict]) -> pd.DataFrame:
    if not transactions:
        return pd.DataFrame(columns=['date', 'label', 'amount'])

    df = pd.DataFrame(transactions)

    df['date'] = pd.to_datetime(df['date'])
    df['amount'] = df['amount'].astype(float)
    df['label'] = df['label'].apply(clean_label)

    return df[['date', 'label', 'amount']]


def clean_label(label: str) -> str:
    label = re.sub(r'[^\w\s]', ' ', label)
    label = re.sub(r'\s+', ' ', label)
    return label.strip().upper()


def format_for_sheets(df: pd.DataFrame, start_row: int) -> List[List]:
    if df.empty:
        return []

    result = []
    for idx, row in df.iterrows():
        current_row = start_row + len(result)
        date_tri = row['date'].strftime('%m/%y')
        label = row['label']
        amount = round(row['amount'], 2)
        date_operation = row['date'].strftime('%d/%m/%Y')

        formula_col_f = f"=IFERROR(INDEX('Catégorisation'!B:B; MATCH(E{current_row}; 'Catégorisation'!C:C; 0)); \"\")"
        formula_col_g = f"=IFERROR(INDEX('Catégorisation'!A:A; MATCH(E{current_row}; 'Catégorisation'!C:C; 0)); \"\")"

        result.append([date_tri, label, amount, date_operation, "", formula_col_f, formula_col_g])

    return result
