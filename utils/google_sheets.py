import gspread
from google.oauth2.service_account import Credentials
import json
import os
from fastapi import HTTPException
import pandas as pd
from utils.config import settings
from utils.sheets_helper import format_for_sheets


class GoogleSheetsClient:
    def __init__(self):
        self.client = self._get_client()

    @staticmethod
    def _get_credentials():
        credentials_json = os.environ.get('GOOGLE_CREDENTIALS_JSON')

        if not credentials_json:
            raise ValueError("Missing environment variable: GOOGLE_CREDENTIALS_JSON")

        try:
            credentials_dict = json.loads(credentials_json)
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Invalid Google credentials JSON: {str(e)}"
            )

        return Credentials.from_service_account_info(
            credentials_dict,
            scopes=settings.GOOGLE_SCOPES
        )

    @staticmethod
    def _get_client():
        try:
            credentials = GoogleSheetsClient._get_credentials()
            return gspread.authorize(credentials)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to connect to Google Sheets: {str(e)}"
            )

    def append_transactions(self, df: pd.DataFrame) -> int:
        spreadsheet_id = os.environ.get('SPREADSHEET_ID')
        sheet_name = os.environ.get('SHEET_NAME')

        if not spreadsheet_id or not sheet_name:
            raise ValueError("Missing environment variables: SPREADSHEET_ID or SHEET_NAME")

        if df.empty:
            return 0

        try:
            spreadsheet = self.client.open_by_key(spreadsheet_id)
            worksheet = spreadsheet.worksheet(sheet_name)

            existing_rows = worksheet.get_all_values()
            existing_keys = self._existing_keys(existing_rows)

            # Now that the daily fetch pulls a multi-day window (to absorb
            # the bank's settlement lag) instead of just "today", the same
            # transaction can show up on several consecutive runs. Skip
            # anything that matches an already-written (date, label, amount).
            df = df[~df.apply(
                lambda row: (
                    row['date'].strftime('%d/%m/%Y'),
                    row['label'],
                    round(row['amount'], 2)
                ) in existing_keys,
                axis=1
            )]

            if df.empty:
                return 0

            start_row = len(existing_rows) + 1
            values = format_for_sheets(df, start_row)

            worksheet.append_rows(values, value_input_option='USER_ENTERED')
            end_row = start_row + len(values) - 1

            self._format_rows(worksheet, start_row, end_row)

            return len(values)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to append transactions: {str(e)}"
            )

    @staticmethod
    def _existing_keys(rows: list) -> set:
        """Build a set of (date_operation, label, amount) already present
        in the sheet, to dedupe against before appending."""
        keys = set()
        for row in rows:
            if len(row) < 4:
                continue
            label = row[1].strip()
            date_operation = row[3].strip()
            try:
                amount = round(float(row[2].strip().replace(',', '.').replace(' ', '')), 2)
            except ValueError:
                continue
            keys.add((date_operation, label, amount))
        return keys

    @staticmethod
    def _format_rows(worksheet, start_row: int, end_row: int):
        requests = [
            {
                "repeatCell": {
                    "range": {
                        "sheetId": worksheet.id,
                        "startRowIndex": start_row - 1,
                        "endRowIndex": end_row,
                        "startColumnIndex": 3,
                        "endColumnIndex": 4
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "horizontalAlignment": "RIGHT"
                        }
                    },
                    "fields": "userEnteredFormat.horizontalAlignment"
                }
            },
            {
                "updateBorders": {
                    "range": {
                        "sheetId": worksheet.id,
                        "startRowIndex": start_row - 1,
                        "endRowIndex": end_row,
                        "startColumnIndex": 0,
                        "endColumnIndex": 4
                    },
                    "top": {"style": "SOLID", "width": 1},
                    "bottom": {"style": "SOLID", "width": 1},
                    "left": {"style": "SOLID", "width": 1},
                    "right": {"style": "SOLID", "width": 1},
                    "innerHorizontal": {"style": "SOLID", "width": 1},
                    "innerVertical": {"style": "SOLID", "width": 1}
                }
            },
            {
                "updateBorders": {
                    "range": {
                        "sheetId": worksheet.id,
                        "startRowIndex": start_row - 1,
                        "endRowIndex": end_row,
                        "startColumnIndex": 5,
                        "endColumnIndex": 7
                    },
                    "top": {"style": "SOLID", "width": 1},
                    "bottom": {"style": "SOLID", "width": 1},
                    "left": {"style": "SOLID", "width": 1},
                    "right": {"style": "SOLID", "width": 1},
                    "innerHorizontal": {"style": "SOLID", "width": 1},
                    "innerVertical": {"style": "SOLID", "width": 1}
                }
            }
        ]

        worksheet.spreadsheet.batch_update({"requests": requests})
