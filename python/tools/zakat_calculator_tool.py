import json
from ..helpers.tool import Tool, Response

class ZakatCalculatorTool(Tool):
    # Nisab threshold in grams of gold (approximately)
    GOLD_NISAB_GRAMS = 87.48
    
    # Default BDT to USD conversion rate (should be updated regularly)
    DEFAULT_BDT_TO_USD = 0.0091  # Example rate: 1 BDT = 0.0091 USD
    
    async def execute(self, assets=None, gold_price=None, currency="BDT", **kwargs):
        """Calculate Zakat based on provided assets."""
        try:
            if not assets or not isinstance(assets, (dict, str)):
                return Response(
                    message="অনুগ্রহ করে সম্পদের তথ্য সঠিক ফরম্যাটে প্রদান করুন।",
                    break_loop=False
                )

            # Convert string to dict if needed
            if isinstance(assets, str):
                try:
                    assets = json.loads(assets)
                except json.JSONDecodeError:
                    return Response(
                        message="সম্পদের ফরম্যাট সঠিক নয়। অনুগ্রহ করে একটি বৈধ JSON অবজেক্ট প্রদান করুন।",
                        break_loop=False
                    )

            # Validate gold price
            if not gold_price or not str(gold_price).replace(".", "").isdigit():
                return Response(
                    message=f"অনুগ্রহ করে প্রতি গ্রাম স্বর্ণের বর্তমান মূল্য {currency}-তে প্রদান করুন।",
                    break_loop=False
                )

            gold_price = float(gold_price)
            nisab_value = self.GOLD_NISAB_GRAMS * gold_price

            # Calculate total wealth
            total_wealth = sum(float(value) for value in assets.values())

            # Prepare asset categories in Bangla
            asset_categories_bn = {
                "savings": "সঞ্চয়",
                "cash": "নগদ",
                "investments": "বিনিয়োগ",
                "gold_jewelry": "স্বর্ণালংকার",
                "silver": "রূপা",
                "business_goods": "ব্যবসায়িক পণ্য",
                "rental_income": "ভাড়া থেকে আয়",
                "agricultural_produce": "কৃষিজ উৎপাদন",
                "stocks": "শেয়ার",
                "mutual_funds": "মিউচুয়াল ফান্ড",
                "fixed_deposits": "স্থায়ী আমানত",
                "receivables": "প্রাপ্য অর্থ"
            }

            # Calculate Zakat if wealth exceeds nisab
            if total_wealth >= nisab_value:
                zakat_amount = total_wealth * 0.025  # 2.5% of total wealth
                
                # Format assets with Bangla categories
                formatted_assets = {}
                for key, value in assets.items():
                    bn_key = asset_categories_bn.get(key, key)
                    formatted_assets[bn_key] = float(value)

                result = {
                    "total_assets": total_wealth,
                    "nisab_threshold": nisab_value,
                    "zakat_due": True,
                    "zakat_amount": zakat_amount,
                    "currency": currency,
                    "breakdown": {
                        "assets": formatted_assets,
                        "calculations": {
                            "মোট সম্পদ": total_wealth,
                            "নিসাব মূল্য": nisab_value,
                            "যাকাতের হার": "২.৫%",
                            "যাকাত গণনা": f"{total_wealth} × ০.০২৫ = {zakat_amount}"
                        }
                    },
                    "message": f"""
                    যাকাত প্রদান করতে হবে। 
                    মোট সম্পদ: {total_wealth:,.2f} {currency}
                    নিসাব সীমা: {nisab_value:,.2f} {currency}
                    প্রদেয় যাকাত: {zakat_amount:,.2f} {currency}
                    """
                }
            else:
                result = {
                    "total_assets": total_wealth,
                    "nisab_threshold": nisab_value,
                    "zakat_due": False,
                    "currency": currency,
                    "message": f"""
                    আপনার মোট সম্পদ ({total_wealth:,.2f} {currency}) নিসাব সীমা ({nisab_value:,.2f} {currency}) অতিক্রম করেনি।
                    এই অবস্থায় যাকাত প্রদান করা ফরয নয়।
                    """
                }

            return Response(message=json.dumps(result), break_loop=False)

        except Exception as e:
            return Response(
                message=f"যাকাত গণনায় ত্রুটি: {str(e)}",
                break_loop=False
            ) 