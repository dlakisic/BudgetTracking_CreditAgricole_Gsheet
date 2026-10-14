from datetime import date, timedelta
from typing import Optional
from fastapi import FastAPI, HTTPException
from mangum import Mangum
from utils.credit_agricole import CreditAgricoleClient
from utils.google_sheets import GoogleSheetsClient
from utils.sheets_helper import process_transactions, format_for_sheets
from utils.logger import setup_logger

app = FastAPI()
logger = setup_logger()

# Credit Agricole's "operations imputees" endpoint (what cragr scrapes)
# reflects settled/booked transactions, which can lag a few days behind
# the actual purchase date. Looking back this far each day (instead of
# just "today") catches those once they finally show up. Safe to widen:
# GoogleSheetsClient.append_transactions() dedupes against what's already
# in the sheet, so re-seeing the same transaction on several runs is a no-op.
DEFAULT_LOOKBACK_DAYS = 6


@app.post("/fetch-transactions")
async def fetch_transactions(date_start: Optional[str] = None, date_stop: Optional[str] = None):
    try:
        # date_start/date_stop (query params, YYYY-MM-DD) are for manual
        # backfills. The daily cron never sends them, so it falls back to
        # the DEFAULT_LOOKBACK_DAYS window ending today.
        parsed_start = date.fromisoformat(date_start) if date_start else date.today() - timedelta(days=DEFAULT_LOOKBACK_DAYS)
        parsed_stop = date.fromisoformat(date_stop) if date_stop else date.today()

        logger.info("Starting transaction fetch")
        transactions = CreditAgricoleClient.get_transactions(
            date_start=parsed_start,
            date_stop=parsed_stop,
        )
        logger.info(f"Fetched {len(transactions)} transactions")

        logger.info("Processing transactions")
        df = process_transactions(transactions)

        logger.info("Appending to Google Sheets")
        sheets_client = GoogleSheetsClient()
        rows_added = sheets_client.append_transactions(df)

        logger.info(f"Successfully added {rows_added} transactions")
        return {
            "status": "success",
            "message": f"Added {rows_added} transactions"
        }

    except Exception as e:
        logger.error(f"Error processing transactions: {str(e)}", exc_info=True)
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


handler = Mangum(app)
