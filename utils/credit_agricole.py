import os
from fastapi import HTTPException
from pydantic import BaseModel
from typing import List, Dict
from datetime import datetime
from creditagricole_particuliers import Authenticator, Operations


class BankAccountConfig(BaseModel):
    account_number: str
    password: List[int]
    region: str


class CreditAgricoleClient:
    @staticmethod
    def _get_config() -> BankAccountConfig:
        account_number = os.environ.get('CA_ACCOUNT_NUMBER')
        password_str = os.environ.get('CA_PASSWORD')
        region = os.environ.get('CA_REGION')

        if not all([account_number, password_str, region]):
            raise ValueError(
                "Missing environment variables: CA_ACCOUNT_NUMBER, CA_PASSWORD, CA_REGION"
            )

        try:
            password = [int(x.strip()) for x in password_str.split(',')]
        except ValueError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Invalid configuration format: {str(e)}"
            )

        return BankAccountConfig(
            account_number=account_number,
            password=password,
            region=region
        )

    @staticmethod
    def get_transactions() -> List[Dict]:
        try:
            config = CreditAgricoleClient._get_config()

            session = Authenticator(
                username=config.account_number,
                password=config.password,
                region=config.region
            )

            date_today = datetime.today().strftime('%Y-%m-%d')
            date_start = date_today
            date_stop = date_today

            operations = Operations(
                session=session,
                date_start=date_start,
                date_stop=date_stop
            )

            return [
                {
                    "date": datetime.strptime(op['dateOperation'], '%b %d, %Y, %H:%M:%S %p').strftime("%Y-%m-%d"),
                    "label": op['libelleOperation'],
                    "amount": float(op['montant'])
                }
                for op in operations.list
            ]
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch transactions: {str(e)}"
            )
