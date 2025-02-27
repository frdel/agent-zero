### zakat_calculator_tool:
Calculate Zakat obligations based on provided assets, liabilities, and current precious metal prices.

Features:
- Calculates if Zakat is due based on Nisab threshold (87.48g gold or 612.36g silver value)
- Computes Zakat amount (2.5% for most assets, different rates for specific categories)
- Supports multiple asset categories:
  - Cash and Bank Assets (cash_in_hand, bank_deposits)
  - Loans Given (loans_given)
  - Investments (shares_investments)
  - Precious Metals (gold_weight/value, silver_weight/value)
  - Trade Goods (trade_goods)
  - Agricultural Assets (irrigated_crops: 5%, rain_fed_crops: 10%)
  - Mining Resources (mining_resources: 20%)
  - Investment Properties (investment_properties)
  - Other Income (other_income)
- Handles liabilities (borrowed_money, dues, expenses)
- Checks Hawl completion (lunar year requirement)
- Provides detailed breakdown in both Bengali and English
- Supports multiple currencies (default: BDT)
- Dynamic precious metal prices for accurate Nisab calculation

Usage:
Provide the following parameters:
- assets: Dictionary of assets and their values
- liabilities: (Optional) Dictionary of liabilities
- currency: (Optional) Currency code (default: "BDT")
- asset_dates: (Optional) Dictionary of asset acquisition dates for Hawl calculation
- language: (Optional) Language preference ("bn" for Bengali, "en" for English)
- gold_price: (Optional) Current gold price per gram in specified currency (default: 12464)
- silver_price: (Optional) Current silver price per gram in specified currency (default: 152)

Example:
~~~json
{
    "thoughts": [
        "Need to calculate Zakat for user's assets and liabilities",
        "Will use current precious metal prices for accurate Nisab calculation"
    ],
    "tool_name": "zakat_calculator_tool",
    "tool_args": {
        "assets": {
            "cash_in_hand": 100000,
            "bank_deposits": 500000,
            "gold_weight": 50,
            "trade_goods": 200000
        },
        "liabilities": {
            "borrowed_money": 50000,
            "dues": 20000
        },
        "currency": "BDT",
        "gold_price": 12464,
        "silver_price": 152,
        "language": "bn",
    }
}
~~~

Response includes:
- Current precious metal prices and Nisab thresholds
- Detailed breakdown of provided assets and liabilities
- Total assets, liabilities, and net wealth calculation
- Nisab status check based on current prices
- Detailed Zakat calculation by category
- Total Zakat due (if applicable)
- Important notes and considerations
- Calculation date
