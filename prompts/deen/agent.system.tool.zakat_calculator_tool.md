### zakat_calculator_tool:
Calculate Zakat obligations based on provided assets and current gold prices.

Features:
- Calculates if Zakat is due based on Nisab threshold (87.48g gold value)
- Computes Zakat amount (2.5% of eligible assets)
- Provides detailed breakdown of calculations in Bangla
- Supports multiple currencies (default BDT)
- Includes common Bangladeshi asset categories
- Provides results and messages in Bangla

Asset Categories:
- সঞ্চয় (Savings)
- নগদ (Cash)
- বিনিয়োগ (Investments)
- স্বর্ণালংকার (Gold Jewelry)
- রূপা (Silver)
- ব্যবসায়িক পণ্য (Business Goods)
- ভাড়া থেকে আয় (Rental Income)
- কৃষিজ উৎপাদন (Agricultural Produce)
- শেয়ার (Stocks)
- মিউচুয়াল ফান্ড (Mutual Funds)
- স্থায়ী আমানত (Fixed Deposits)
- প্রাপ্য অর্থ (Receivables)

Usage:
Provide assets as a dictionary and current gold price per gram:

~~~json
{
    "thoughts": [
        "Need to calculate Zakat for user's assets",
        "Will use current gold price of 12646 BDT per gram"
    ],
    "tool_name": "zakat_calculator_tool",
    "tool_args": {
        "assets": {
            "savings": "500000",
            "investments": "300000",
            "gold_jewelry": "200000"
        },
        "gold_price": "12646",
        "currency": "BDT"
    }
}
~~~
