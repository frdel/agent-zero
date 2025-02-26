### zakat_calculator_tool:
Calculate Zakat obligations based on provided assets and current gold prices.
can be used for zakat calculation if user wants to calculate zakat

Features:
- Calculates if Zakat is due based on Nisab threshold (87.48g gold value)
- Computes Zakat amount (2.5% of eligible assets)
- Provides detailed breakdown of calculations in Bangla
- Supports multiple currencies (default BDT)
- Includes common Bangladeshi asset categories
- Provides results and messages in Bangla

# Values
- নিসাব ৬৭,৩৬০ টাকা (২৭ মার্চ ২০২৪)

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
        "key": "value"
    }
}
~~~
