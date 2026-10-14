import logging
import os
from datetime import date
from fastapi import HTTPException
from pydantic import BaseModel
from typing import List, Dict

from woob.core import WoobBase
from woob.browser.exceptions import HTTPNotFound, ClientError, ServerError
from woob.exceptions import BrowserIncorrectPassword, BrowserUnavailable

logger = logging.getLogger(__name__)

# Directory bundled alongside the Lambda code/layer, containing the
# `cragr` woob module (see woob_modules/cragr/). Kept local instead of
# fetched from updates.woob.tech at runtime so a deploy is reproducible
# and doesn't depend on that service being reachable/trusted from Lambda.
WOOB_MODULES_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'woob_modules')


class BankAccountConfig(BaseModel):
    account_number: str
    password: str
    website: str


class CreditAgricoleClient:
    @staticmethod
    def _get_config() -> BankAccountConfig:
        account_number = os.environ.get('CA_ACCOUNT_NUMBER')
        password = os.environ.get('CA_PASSWORD')
        website = os.environ.get('CA_WEBSITE')

        if not all([account_number, password, website]):
            raise ValueError(
                "Missing environment variables: CA_ACCOUNT_NUMBER, CA_PASSWORD, CA_WEBSITE"
            )

        return BankAccountConfig(
            account_number=account_number,
            password=password,
            website=website
        )

    @staticmethod
    def get_transactions(date_start: date = None, date_stop: date = None) -> List[Dict]:
        config = CreditAgricoleClient._get_config()
        today = date.today()
        # Default behaviour (daily cron): only today's transactions.
        # A range can be passed for one-off backfills.
        date_start = date_start or today
        date_stop = date_stop or today

        woob = WoobBase(modules_path=WOOB_MODULES_PATH)
        try:
            backend = woob.build_backend(
                'cragr',
                params={
                    'website': config.website,
                    'login': config.account_number,
                    'password': config.password,
                },
                name='cragr'
            )
            try:
                transactions = []
                for account in backend.iter_accounts():
                    for tr in backend.iter_history(account):
                        if not (date_start <= tr.date <= date_stop):
                            continue
                        transactions.append({
                            "date": tr.date.strftime('%Y-%m-%d'),
                            "label": tr.label or tr.raw,
                            "amount": float(tr.amount),
                        })
                return transactions
            finally:
                backend.deinit()

        except (BrowserIncorrectPassword, BrowserUnavailable) as e:
            raise HTTPException(
                status_code=401,
                detail=f"Credit Agricole authentication failed: {str(e)}"
            )
        except Exception as e:
            if isinstance(e, (ClientError, ServerError, HTTPNotFound)) and getattr(e, 'response', None) is not None:
                CreditAgricoleClient._log_http_error(e.response)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch transactions: {str(e)}"
            )
        finally:
            woob.deinit()

    @staticmethod
    def _log_http_error(response) -> None:
        """Log enough of a failed bank request to diagnose site changes,
        without cookies, auth tokens or the request body (which can hold
        the account number / keypad positions)."""
        hidden = {'cookie', 'set-cookie', 'authorization', 'x-xsrf-token', 'x-auth-login'}
        req = response.request
        logger.error(
            "Bank HTTP error: %s %s -> %s\nrequest headers: %s\nresponse headers: %s\nresponse body: %s",
            req.method, req.url, response.status_code,
            {k: v for k, v in req.headers.items() if k.lower() not in hidden},
            {k: v for k, v in response.headers.items() if k.lower() not in hidden},
            response.text[:2000],
        )
