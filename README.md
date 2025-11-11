# Budget Tracking - Crédit Agricole to Google Sheets

Daily sync of Crédit Agricole transactions to Google Sheets for budget tracking.

## Architecture

Serverless on AWS Free Tier ($0/month):

- **AWS Lambda** (Python 3.13) - Transaction processing
- **AWS EventBridge** - Daily trigger at 22h59/23h59 Paris time
- **Lambda Layers** - Dependencies (6.5MB)
- **FastAPI + Mangum** - REST API
- **Google Sheets API** - Dashboard with categorization formulas

## Features

- Daily sync of bank transactions
- Data formatting (dates, amounts, labels)
- Automatic categorization with INDEX/MATCH formulas
- Google Sheets formatting (borders, alignment)
- Clean Code principles
- Full type hints
- Error handling and CloudWatch logging
- **$0/month**

## Project Structure

```
.
├── lambda_function.py       # Lambda entry point with FastAPI
├── utils/
│   ├── credit_agricole.py  # Bank API client (creditagricole-particuliers v0.2.0)
│   ├── google_sheets.py    # Google Sheets client with formatting
│   ├── sheets_helper.py    # Data processing and formula generation
│   ├── logger.py           # CloudWatch logging setup
│   └── config.py           # Application settings
├── layer-slim/             # Lambda Layer source (dependencies)
├── lambda-code.zip         # Deployed Lambda code (4.6KB)
├── lambda-layer-slim.zip   # Deployed Lambda Layer (6.5MB)
├── env-vars.json           # AWS Lambda environment variables (git-ignored)
├── requirements.txt        # Python dependencies
├── Makefile               # Deployment commands
└── README.md              # This file
```

## Prerequisites

- Python 3.13
- AWS CLI configured with credentials
- Google Cloud Service Account with Sheets API enabled
- Crédit Agricole bank account

## Setup

### 1. Clone Repository

```bash
git clone https://github.com/dlakisic/BudgetTracking_CreditAgricole_Gsheet.git
cd BudgetTracking_CreditAgricole_Gsheet
```

### 2. Configure Environment Variables

Copy `env-vars.json.example` to `env-vars.json` and fill in your credentials:

```bash
cp env-vars.json.example env-vars.json
```

**Environment Variables:**

| Variable | Description | Example |
|----------|-------------|---------|
| `SPREADSHEET_ID` | Google Sheets ID from URL | `1ABCD...` |
| `SHEET_NAME` | Worksheet name | `Opérations` |
| `GOOGLE_CREDENTIALS_JSON` | Service account JSON (single line) | `{"type":"service_account"...}` |
| `CA_ACCOUNT_NUMBER` | Bank account number | `12345678901` |
| `CA_PASSWORD` | PIN as comma-separated digits | `1,2,3,4,5,6` |
| `CA_REGION` | Regional bank code | `bretagne`, `paris`, etc. |

### 3. Google Service Account Setup

1. Create Service Account in [Google Cloud Console](https://console.cloud.google.com/)
2. Enable **Google Sheets API** and **Google Drive API**
3. Download JSON key file
4. Convert to single line: `cat key.json | jq -c '.'`
5. Share your Google Sheet with the service account email

### 4. Build Lambda Layer

```bash
mkdir -p layer-slim/python
pip install -r requirements.txt -t layer-slim/python/ --python-version 3.13 --only-binary=:all:
cd layer-slim && zip -r ../lambda-layer-slim.zip python/ && cd ..
```

### 5. Deploy to AWS

```bash
# Publish Lambda Layer
aws lambda publish-layer-version \
  --layer-name budget-tracking-deps \
  --zip-file fileb://lambda-layer-slim.zip \
  --compatible-runtimes python3.13 \
  --region eu-west-3

# Package Lambda code
zip -r lambda-code.zip lambda_function.py utils/

# Create/Update Lambda function
aws lambda update-function-code \
  --function-name BudgetTracking-CA \
  --zip-file fileb://lambda-code.zip \
  --region eu-west-3

# Configure environment variables
aws lambda update-function-configuration \
  --function-name BudgetTracking-CA \
  --environment file://env-vars.json \
  --region eu-west-3

# Attach Lambda Layer
aws lambda update-function-configuration \
  --function-name BudgetTracking-CA \
  --layers arn:aws:lambda:eu-west-3:336392948345:layer:AWSSDKPandas-Python313:1 \
           arn:aws:lambda:eu-west-3:YOUR_ACCOUNT_ID:layer:budget-tracking-deps:1 \
  --region eu-west-3
```

### 6. Configure EventBridge Schedule

```bash
# Create daily trigger rule (21h59 UTC = 22h59/23h59 Paris)
aws events put-rule \
  --name BudgetTracking-DailySync \
  --schedule-expression "cron(59 21 * * ? *)" \
  --region eu-west-3

# Grant EventBridge permission to invoke Lambda
aws lambda add-permission \
  --function-name BudgetTracking-CA \
  --statement-id EventBridgeDailyInvoke \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn arn:aws:events:eu-west-3:YOUR_ACCOUNT_ID:rule/BudgetTracking-DailySync \
  --region eu-west-3

# Add Lambda as target
aws events put-targets \
  --rule BudgetTracking-DailySync \
  --targets file://eventbridge-targets.json \
  --region eu-west-3
```

## Usage

### Manual Invocation

```bash
aws lambda invoke \
  --function-name BudgetTracking-CA \
  --cli-binary-format raw-in-base64-out \
  --payload '{"version":"2.0","routeKey":"POST /fetch-transactions","rawPath":"/fetch-transactions","headers":{"content-type":"application/json"},"requestContext":{"http":{"method":"POST","path":"/fetch-transactions"}},"body":"","isBase64Encoded":false}' \
  --region eu-west-3 \
  output.json
```

### View Logs

```bash
aws logs tail /aws/lambda/BudgetTracking-CA --since 10m --follow --region eu-west-3
```

### Disable Automatic Sync

```bash
aws events disable-rule --name BudgetTracking-DailySync --region eu-west-3
```

## Google Sheets Output

Columns written by the Lambda:

| Column | Content | Format |
|--------|---------|--------|
| A | Date tri | `mm/yy` |
| B | Libellé | Uppercase, cleaned |
| C | Montant | Rounded to 2 decimals |
| D | Date opération | `dd/mm/yyyy` |
| E | (Empty) | Manual categorization input |
| F | Catégorie | Formula: `=IFERROR(INDEX('Catégorisation'!B:B; MATCH(E{row}; 'Catégorisation'!C:C; 0)); "")` |
| G | Sous-catégorie | Formula: `=IFERROR(INDEX('Catégorisation'!A:A; MATCH(E{row}; 'Catégorisation'!C:C; 0)); "")` |

Borders on cells A-D and F-G, column D right-aligned. Formulas reference the 'Catégorisation' sheet.

## Development

### Tech Stack

| Technology | Purpose |
|------------|---------|
| Python 3.13 | Runtime |
| FastAPI | REST framework |
| Mangum | ASGI adapter for Lambda |
| gspread | Google Sheets client |
| google-auth | OAuth2 authentication |
| pydantic | Data validation |
| pandas | Data processing |
| creditagricole-particuliers | Bank API client (v0.2.0) |

## Cost

**$0/month** (AWS Free Tier)

| Service | Usage | Cost |
|---------|-------|------|
| AWS Lambda | 1 invocation/day (~30/month) | Free tier (1M requests/month) |
| Lambda Layer | 6.5MB storage | Free tier |
| EventBridge | 1 rule, 30 invocations/month | Free tier (unlimited rules) |
| CloudWatch Logs | ~1MB/month | Free tier (5GB/month) |
| Environment Variables | Encrypted at rest (KMS) | Free |

## Technical Decisions

**Lambda Layers**: Separates 6.5MB of dependencies from 4.6KB code for faster deployments.

**creditagricole-particuliers v0.2.0**: v0.14.3 has breaking API changes.

**Environment Variables**: Free alternative to Secrets Manager. Still encrypted at rest.

**EventBridge**: Native scheduler, no extra Lambda needed.

## Troubleshooting

**"No module named 'fastapi'"**: Check Lambda Layer is attached:
```bash
aws lambda get-function-configuration --function-name BudgetTracking-CA --region eu-west-3 --query 'Layers[*].Arn'
```

**Invalid Google credentials**: Convert JSON to single line:
```bash
cat credentials.json | jq -c '.' | jq -R -s '.'
```

**No transactions in Sheets**: Check CloudWatch logs:
```bash
aws logs tail /aws/lambda/BudgetTracking-CA --since 1h --region eu-west-3
```

**pydantic_core binary error**: Rebuild layer with `--python-version 3.13 --only-binary=:all:`

## Security

- IAM role with least-privilege permissions
- Google Service Account with minimal scopes

## License

Personal use only.

## Author

**Dino Lakisic**
- GitHub: [@dlakisic](https://github.com/dlakisic)
- Email: dino.lakisic@gmail.com

## Credits

- [python-creditagricole-particuliers](https://github.com/dmachard/python-creditagricole-particuliers) v0.2.0 by dmachard
