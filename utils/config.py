from typing import List


class Settings:
    GOOGLE_SCOPES: List[str] = [
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive'
    ]


settings = Settings() 