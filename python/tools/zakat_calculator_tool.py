import json
from datetime import datetime
from hijri_converter.convert import Gregorian, Hijri
from ..helpers.tool import Tool, Response

class ZakatCalculatorTool(Tool):
    # Nisab thresholds
    GOLD_NISAB_GRAMS = 87.48
    SILVER_NISAB_GRAMS = 612.36
    
    # Current precious metal prices
    GOLD_PRICE = 12464  # Price per gram for gold
    SILVER_PRICE = 152  # Price per gram for silver
    
    # Current Nisab values in BDT (as of March 27, 2024)
    GOLD_NISAB_BDT = GOLD_NISAB_GRAMS * GOLD_PRICE  # 1,090,370.72 BDT
    SILVER_NISAB_BDT = SILVER_NISAB_GRAMS * SILVER_PRICE    # 93,078.72 BDT
    CURRENT_NISAB_BDT = min(GOLD_NISAB_BDT, SILVER_NISAB_BDT)  # Use the lower of gold and silver nisab
    
    # Zakat rates for different asset types
    ZAKAT_RATES = {
        "default": 0.025,  # 2.5% for most assets
        "irrigated_crops": 0.05,  # 5% for irrigated agricultural produce
        "rain_fed_crops": 0.10,  # 10% for rain-fed agricultural produce
        "mining": 0.20,  # 20% for mining and extracted resources
    }
    
    # Asset categories with English and Bangla names
    ASSET_CATEGORIES = {
        # Cash and Bank Assets
        "cash_in_hand": {"bn": "নগদ টাকা", "rate": "default"},
        "bank_deposits": {"bn": "ব্যাংক জমা", "rate": "default"},
        
        # Loans Given
        "loans_given": {"bn": "প্রদত্ত ঋণ", "rate": "default"},
        
        # Investments
        "shares_investments": {"bn": "শেয়ার ও বিনিয়োগ", "rate": "default"},
        
        # Precious Metals
        "gold_weight": {"bn": "স্বর্ণের ওজন (গ্রাম)", "rate": "default"},
        "gold_value": {"bn": "স্বর্ণের মূল্য", "rate": "default"},
        "silver_weight": {"bn": "রূপার ওজন (গ্রাম)", "rate": "default"},
        "silver_value": {"bn": "রূপার মূল্য", "rate": "default"},
        
        # Trade Goods
        "trade_goods": {"bn": "ব্যবসায়িক পণ্য", "rate": "default"},
        
        # Agricultural Assets
        "irrigated_crops": {"bn": "সেচকৃত ফসল", "rate": "irrigated_crops"},
        "rain_fed_crops": {"bn": "বৃষ্টি নির্ভর ফসল", "rate": "rain_fed_crops"},
        
        # Mining and Resources
        "mining_resources": {"bn": "খনিজ সম্পদ", "rate": "mining"},
        
        # Investment Properties
        "investment_properties": {"bn": "বিনিয়োগী সম্পত্তি", "rate": "default"},
        
        # Other Income
        "other_income": {"bn": "অন্যান্য আয়", "rate": "default"}
    }
    
    # Liabilities categories
    LIABILITIES_CATEGORIES = {
        "borrowed_money": "ধার করা টাকা",
        "dues": "বাকি বিল ও পেমেন্ট",
        "expenses": "খরচ"
    }

    def _calculate_precious_metal_value(self, assets):
        """Calculate the total value of precious metals from weight or direct value."""
        total_value = 0
        
        # Calculate gold value
        if "gold_weight" in assets:
            total_value += float(assets["gold_weight"]) * self.GOLD_PRICE
            assets["gold_value"] = total_value
            del assets["gold_weight"]
        elif "gold_value" in assets:
            total_value += float(assets["gold_value"])
            
        # Calculate silver value
        if "silver_weight" in assets:
            total_value += float(assets["silver_weight"]) * self.SILVER_PRICE
            assets["silver_value"] = total_value
            del assets["silver_weight"]
        elif "silver_value" in assets:
            total_value += float(assets["silver_value"])
            
        return total_value

    def _check_hawl(self, asset_date):
        """Check if a complete lunar year (Hawl) has passed."""
        if not asset_date:
            return True  # If no date provided, assume Hawl is complete
            
        try:
            # Convert asset date to Hijri
            asset_greg = datetime.strptime(asset_date, "%Y-%m-%d")
            asset_hijri = Gregorian(asset_greg.year, asset_greg.month, asset_greg.day).to_hijri()
            
            # Get current date in Hijri
            today = datetime.now()
            current_hijri = Gregorian(today.year, today.month, today.day).to_hijri()
            
            # Calculate difference in years
            year_diff = current_hijri.year - asset_hijri.year
            if year_diff == 0:
                return False
            elif year_diff == 1:
                # Check if a complete year has passed
                if current_hijri.month < asset_hijri.month:
                    return False
                elif current_hijri.month == asset_hijri.month:
                    return current_hijri.day >= asset_hijri.day
                return True
            return True
            
        except Exception:
            return True  # If date parsing fails, assume Hawl is complete
    
    async def execute(self, assets=None, liabilities=None, currency="BDT", asset_dates=None, **kwargs):
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

            # Convert asset_dates string to dict if needed
            if isinstance(asset_dates, str):
                try:
                    asset_dates = json.loads(asset_dates) if asset_dates else {}
                except json.JSONDecodeError:
                    asset_dates = {}
            elif asset_dates is None:
                asset_dates = {}

            # Calculate precious metal values
            self._calculate_precious_metal_value(assets)

            # Calculate total wealth with specific rates
            total_assets = 0
            zakat_by_category = {}
            
            for asset_key, value in assets.items():
                if asset_key in self.ASSET_CATEGORIES:
                    # Check if Hawl is complete for this asset
                    if self._check_hawl(asset_dates.get(asset_key)):
                        asset_value = float(value)
                        rate_key = self.ASSET_CATEGORIES[asset_key]["rate"]
                        rate = self.ZAKAT_RATES[rate_key]
                        zakat_amount = asset_value * rate
                        
                        total_assets += asset_value
                        zakat_by_category[self.ASSET_CATEGORIES[asset_key]["bn"]] = {
                            "value": asset_value,
                            "rate": rate * 100,
                            "zakat": zakat_amount
                        }

            total_liabilities = sum(float(value) for value in (liabilities or {}).values())
            net_wealth = total_assets - total_liabilities

            # Format assets with Bangla categories
            formatted_assets = {}
            for key, value in assets.items():
                if key in self.ASSET_CATEGORIES:
                    bn_key = self.ASSET_CATEGORIES[key]["bn"]
                    formatted_assets[bn_key] = float(value)

            # Format liabilities with Bangla categories
            formatted_liabilities = {}
            if liabilities:
                for key, value in liabilities.items():
                    bn_key = self.LIABILITIES_CATEGORIES.get(key, key)
                    formatted_liabilities[bn_key] = float(value)

            # Calculate total zakat
            total_zakat = sum(cat["zakat"] for cat in zakat_by_category.values())

            # Prepare result based on nisab threshold
            if net_wealth >= self.CURRENT_NISAB_BDT:
                result = {
                    "total_assets": total_assets,
                    "total_liabilities": total_liabilities,
                    "net_wealth": net_wealth,
                    "nisab_threshold": {
                        "gold": self.GOLD_NISAB_BDT,
                        "silver": self.SILVER_NISAB_BDT,
                        "current": self.CURRENT_NISAB_BDT
                    },
                    "precious_metal_prices": {
                        "gold": {
                            "price_per_gram": self.GOLD_PRICE
                        },
                        "silver": {
                            "price_per_gram": self.SILVER_PRICE
                        }
                    },
                    "zakat_due": True,
                    "total_zakat": total_zakat,
                    "currency": currency,
                    "breakdown": {
                        "assets": formatted_assets,
                        "liabilities": formatted_liabilities,
                        "zakat_by_category": zakat_by_category,
                        "calculations": {
                            "মোট সম্পদ": total_assets,
                            "মোট দায়": total_liabilities,
                            "নীট সম্পদ": net_wealth,
                            "নিসাব সীমা (স্বর্ণ)": self.GOLD_NISAB_BDT,
                            "নিসাব সীমা (রূপা)": self.SILVER_NISAB_BDT,
                            "বর্তমান নিসাব সীমা": self.CURRENT_NISAB_BDT,
                            "মোট যাকাত": total_zakat
                        }
                    },
                    "message": f"""
                    যাকাত প্রদান করতে হবে।
                    
                    সম্পদের হিসাব:
                    ১। মোট সম্পদ: {total_assets:,.2f} {currency}
                    ২। মোট দায়: {total_liabilities:,.2f} {currency}
                    ৩। নীট সম্পদ: {net_wealth:,.2f} {currency}
                    
                    নিসাব সীমা:
                    • স্বর্ণ ({self.GOLD_NISAB_GRAMS} গ্রাম): {self.GOLD_NISAB_BDT:,.2f} {currency}
                    • রূপা ({self.SILVER_NISAB_GRAMS} গ্রাম): {self.SILVER_NISAB_BDT:,.2f} {currency}
                    • বর্তমান নিসাব: {self.CURRENT_NISAB_BDT:,.2f} {currency}
                    
                    যাকাতের হিসাব:
                    {self._format_zakat_breakdown(zakat_by_category, currency)}
                    
                    মোট প্রদেয় যাকাত: {total_zakat:,.2f} {currency}
                    
                    (হিসাব তারিখ: ২৭ মার্চ ২০২৪)
                    """
                }
            else:
                result = {
                    "total_assets": total_assets,
                    "total_liabilities": total_liabilities,
                    "net_wealth": net_wealth,
                    "nisab_threshold": {
                        "gold": self.GOLD_NISAB_BDT,
                        "silver": self.SILVER_NISAB_BDT,
                        "current": self.CURRENT_NISAB_BDT
                    },
                    "precious_metal_prices": {
                        "gold": {
                            "price_per_gram": self.GOLD_PRICE
                        },
                        "silver": {
                            "price_per_gram": self.SILVER_PRICE
                        }
                    },
                    "zakat_due": False,
                    "currency": currency,
                    "message": f"""
                    যাকাত প্রদান করা ফরয নয়।
                    
                    কারণ:
                    • আপনার নীট সম্পদ: {net_wealth:,.2f} {currency}
                    • স্বর্ণের নিসাব সীমা: {self.GOLD_NISAB_BDT:,.2f} {currency}
                    • রূপার নিসাব সীমা: {self.SILVER_NISAB_BDT:,.2f} {currency}
                    • বর্তমান নিসাব সীমা: {self.CURRENT_NISAB_BDT:,.2f} {currency}
                    • আপনার সম্পদ নিসাব সীমা অতিক্রম করেনি
                    
                    (হিসাব তারিখ: ২৭ মার্চ ২০২৪)
                    """
                }

            return Response(message=json.dumps(result), break_loop=False)

        except Exception as e:
            return Response(
                message=f"যাকাত গণনায় ত্রুটি: {str(e)}",
                break_loop=False
            )
            
    def _format_zakat_breakdown(self, zakat_by_category, currency):
        """Format the zakat breakdown message in Bengali."""
        breakdown = []
        for category, data in zakat_by_category.items():
            breakdown.append(
                f"• {category}:\n"
                f"  - মূল্য: {data['value']:,.2f} {currency}\n"
                f"  - হার: {data['rate']}%\n"
                f"  - যাকাত: {data['zakat']:,.2f} {currency}"
            )
        return "\n".join(breakdown) 