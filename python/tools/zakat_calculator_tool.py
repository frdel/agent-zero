import json
from ..helpers.tool import Tool, Response

class ZakatCalculatorTool(Tool):
    # Nisab threshold in grams of gold (approximately)
    GOLD_NISAB_GRAMS = 87.48
    
    # Default BDT to USD conversion rate (should be updated regularly)
    DEFAULT_BDT_TO_USD = 0.0091  # Example rate: 1 BDT = 0.0091 USD
    
    # Asset categories with English and Bangla names
    ASSET_CATEGORIES = {
        # Cash and Bank Assets
        "cash": "নগদ অর্থ",
        "savings": "সঞ্চয়ী হিসাবের অর্থ",
        "current_account": "চলতি হিসাবের অর্থ",
        "fixed_deposits": "স্থায়ী আমানত",
        "foreign_currency": "বৈদেশিক মুদ্রা",
        
        # Loans and Receivables
        "loans_given": "প্রদত্ত ঋণ",
        "business_receivables": "ব্যবসায়িক প্রাপ্য",
        "other_receivables": "অন্যান্য প্রাপ্য",
        
        # Investment Assets
        "stocks": "শেয়ার",
        "mutual_funds": "মিউচুয়াল ফান্ড",
        "business_investments": "ব্যবসায়িক বিনিয়োগ",
        "investment_properties": "বিনিয়োগকৃত সম্পত্তি",
        "other_investments": "অন্যান্য বিনিয়োগ",
        
        # Precious Metals
        "gold_jewelry": "স্বর্ণালংকার",
        "gold_bullion": "স্বর্ণ বার",
        "silver_items": "রূপার সামগ্রী",
        "silver_bullion": "রূপা বার",
        "other_precious_metals": "অন্যান্য মূল্যবান ধাতু",
        
        # Business Assets
        "trading_inventory": "ব্যবসায়িক পণ্য/মজুত",
        "raw_materials": "কাঁচামাল",
        "finished_products": "তৈরি পণ্য",
        "business_equipment": "ব্যবসায়িক সরঞ্জাম",
        
        # Income Properties
        "rental_income": "ভাড়া থেকে আয়",
        "agricultural_income": "কৃষিজ আয়",
        "commercial_property_income": "বাণিজ্যিক সম্পত্তি থেকে আয়"
    }
    
    # Liabilities categories
    LIABILITIES_CATEGORIES = {
        # Essential Debts
        "personal_loans": "ব্যক্তিগত ঋণ",
        "business_loans": "ব্যবসায়িক ঋণ",
        "mortgages": "বন্ধকী ঋণ",
        
        # Due Payments
        "outstanding_bills": "বকেয়া বিল",
        "unpaid_wages": "অপরিশোধিত বেতন",
        "tax_liabilities": "কর দায়",
        "other_dues": "অন্যান্য বকেয়া"
    }
    
    async def execute(self, assets=None, liabilities=None, gold_price=None, currency="BDT", **kwargs):
        """Calculate Zakat based on provided assets and liabilities."""
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

            # Convert liabilities string to dict if needed
            if isinstance(liabilities, str):
                try:
                    liabilities = json.loads(liabilities) if liabilities else {}
                except json.JSONDecodeError:
                    return Response(
                        message="দায়ের ফরম্যাট সঠিক নয়। অনুগ্রহ করে একটি বৈধ JSON অবজেক্ট প্রদান করুন।",
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
            total_assets = sum(float(value) for value in assets.values())
            total_liabilities = sum(float(value) for value in (liabilities or {}).values())
            net_wealth = total_assets - total_liabilities

            # Format assets with Bangla categories
            formatted_assets = {}
            for key, value in assets.items():
                bn_key = self.ASSET_CATEGORIES.get(key, key)
                formatted_assets[bn_key] = float(value)

            # Format liabilities with Bangla categories
            formatted_liabilities = {}
            if liabilities:
                for key, value in liabilities.items():
                    bn_key = self.LIABILITIES_CATEGORIES.get(key, key)
                    formatted_liabilities[bn_key] = float(value)

            # Calculate Zakat if wealth exceeds nisab
            if net_wealth >= nisab_value:
                zakat_amount = net_wealth * 0.025  # 2.5% of net wealth
                
                result = {
                    "total_assets": total_assets,
                    "total_liabilities": total_liabilities,
                    "net_wealth": net_wealth,
                    "nisab_threshold": nisab_value,
                    "zakat_due": True,
                    "zakat_amount": zakat_amount,
                    "currency": currency,
                    "breakdown": {
                        "assets": formatted_assets,
                        "liabilities": formatted_liabilities,
                        "calculations": {
                            "মোট সম্পদ": total_assets,
                            "মোট দায়": total_liabilities,
                            "নীট সম্পদ": net_wealth,
                            "নিসাব মূল্য": nisab_value,
                            "যাকাতের হার": "২.৫%",
                            "যাকাত গণনা": f"{net_wealth} × ০.০২৫ = {zakat_amount}"
                        }
                    },
                    "message": f"""
                    যাকাত প্রদান করতে হবে। 
                    মোট সম্পদ: {total_assets:,.2f} {currency}
                    মোট দায়: {total_liabilities:,.2f} {currency}
                    নীট সম্পদ: {net_wealth:,.2f} {currency}
                    নিসাব সীমা: {nisab_value:,.2f} {currency}
                    প্রদেয় যাকাত: {zakat_amount:,.2f} {currency}
                    """
                }
            else:
                result = {
                    "total_assets": total_assets,
                    "total_liabilities": total_liabilities,
                    "net_wealth": net_wealth,
                    "nisab_threshold": nisab_value,
                    "zakat_due": False,
                    "currency": currency,
                    "message": f"""
                    আপনার নীট সম্পদ ({net_wealth:,.2f} {currency}) নিসাব সীমা ({nisab_value:,.2f} {currency}) অতিক্রম করেনি।
                    এই অবস্থায় যাকাত প্রদান করা ফরয নয়।
                    """
                }

            return Response(message=json.dumps(result), break_loop=False)

        except Exception as e:
            return Response(
                message=f"যাকাত গণনায় ত্রুটি: {str(e)}",
                break_loop=False
            ) 