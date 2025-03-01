import json
from datetime import datetime, timedelta
from ..helpers.tool import Tool, Response

class ZakatCalculatorTool(Tool):
    # Nisab thresholds
    GOLD_NISAB_GRAMS = 87.48
    SILVER_NISAB_GRAMS = 612.36
    
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

    def _calculate_precious_metal_value(self, assets, gold_price, silver_price):
        """Calculate the total value of precious metals from weight or direct value."""
        total_value = 0
        
        # Calculate gold value
        if "gold_weight" in assets:
            total_value += float(assets["gold_weight"]) * gold_price
            assets["gold_value"] = total_value
            del assets["gold_weight"]
        elif "gold_value" in assets:
            total_value += float(assets["gold_value"])
            
        # Calculate silver value
        if "silver_weight" in assets:
            total_value += float(assets["silver_weight"]) * silver_price
            assets["silver_value"] = total_value
            del assets["silver_weight"]
        elif "silver_value" in assets:
            total_value += float(assets["silver_value"])
            
        return total_value

    def _check_hawl(self, date_str):
        """Check if a full Islamic year (Hawl) has passed.
        
        Args:
            date_str (str): Date string in format YYYY-MM-DD
        
        Returns:
            bool: True if Hawl is complete, False otherwise
        """
        if not date_str:
            return True  # If no date is provided, assume Hawl is complete
            
        try:
            # Parse the acquisition date
            acquisition_date = datetime.strptime(date_str, "%Y-%m-%d")
            
            # Calculate the Islamic year (approximately 354.367 days)
            hawl_completion_date = acquisition_date + timedelta(days=354)
            
            # Compare with current date
            return datetime.now() >= hawl_completion_date
        except:
            return True  # If there's an error parsing the date, assume Hawl is complete

    async def execute(self, assets=None, liabilities=None, currency="BDT", asset_dates=None, language="bn", gold_price=12464, silver_price=152, status=None, **kwargs):
        """Calculate Zakat based on provided assets and liabilities.
        
        Args:
            assets (dict): Dictionary of assets and values
            liabilities (dict): Dictionary of liabilities and values
            currency (str): Currency code (default: BDT)
            asset_dates (dict): Dictionary of asset acquisition dates for Hawl calculation
            language (str): Language preference ('bn' for Bengali, 'en' for English)
            gold_price (float): Current gold price per gram
            silver_price (float): Current silver price per gram
            status (str): Optional status - 'success' for successful calculation, 'cancel' for canceled calculation
        """
        try:
            # Ensure assets and liabilities are properly initialized
            if assets is None:
                assets = {}
                
            if liabilities is None:
                liabilities = {}
                
            # Handle status parameter for success or cancel states
            if status == "success":
                if language == "bn":
                    return Response(
                        message="যাকাত গণনা সফলভাবে সম্পন্ন হয়েছে। আপনার যাকাত সম্পর্কিত প্রয়োজনীয় তথ্য প্রদান করা হয়েছে।",
                        break_loop=False
                    )
                else:
                    return Response(
                        message="Zakat calculation successfully completed. Your necessary zakat information has been provided.",
                        break_loop=False
                    )
            
            if status == "cancel":
                if language == "bn":
                    return Response(
                        message="যাকাত হিসাব বাতিল করা হয়েছে। যেকোন সময় আবার যাকাত হিসাব করতে চাইলে জানাবেন।",
                        break_loop=False
                    )
                else:
                    return Response(
                        message="Zakat calculation has been canceled. Feel free to ask for zakat calculation again anytime.",
                        break_loop=False
                    )

            # Convert assets string to dict if needed
            if isinstance(assets, str):
                try:
                    assets = json.loads(assets) if assets else {}
                except json.JSONDecodeError:
                    message = "সম্পদের ফরম্যাট সঠিক নয়। অনুগ্রহ করে একটি বৈধ JSON অবজেক্ট প্রদান করুন।" if language == "bn" else "Invalid assets format. Please provide a valid JSON object."
                    return Response(message=message, break_loop=False)

            # Convert liabilities string to dict if needed
            if isinstance(liabilities, str):
                try:
                    liabilities = json.loads(liabilities) if liabilities else {}
                except json.JSONDecodeError:
                    message = "দায়ের ফরম্যাট সঠিক নয়। অনুগ্রহ করে একটি বৈধ JSON অবজেক্ট প্রদান করুন।" if language == "bn" else "Invalid liabilities format. Please provide a valid JSON object."
                    return Response(message=message, break_loop=False)

            # Convert asset_dates string to dict if needed
            if isinstance(asset_dates, str):
                try:
                    asset_dates = json.loads(asset_dates) if asset_dates else {}
                except json.JSONDecodeError:
                    asset_dates = {}
            elif asset_dates is None:
                asset_dates = {}

            # Calculate Nisab thresholds using current prices
            gold_nisab_value = self.GOLD_NISAB_GRAMS * gold_price
            silver_nisab_value = self.SILVER_NISAB_GRAMS * silver_price
            current_nisab = min(gold_nisab_value, silver_nisab_value)

            # Calculate precious metal values
            self._calculate_precious_metal_value(assets, gold_price, silver_price)

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
            if assets:
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

            # Format the summary based on language
            if language == "bn":
                summary = self._format_bengali_summary(assets, liabilities, zakat_by_category, total_assets, total_liabilities, net_wealth, total_zakat, currency, gold_price, silver_price, gold_nisab_value, silver_nisab_value, current_nisab)
            else:
                summary = self._format_english_summary(assets, liabilities, zakat_by_category, total_assets, total_liabilities, net_wealth, total_zakat, currency, gold_price, silver_price, gold_nisab_value, silver_nisab_value, current_nisab)

            # Prepare result based on nisab threshold
            if net_wealth >= current_nisab:
                result = {
                    "total_assets": total_assets,
                    "total_liabilities": total_liabilities,
                    "net_wealth": net_wealth,
                    "nisab_threshold": {
                        "gold": gold_nisab_value,
                        "silver": silver_nisab_value,
                        "current": current_nisab
                    },
                    "precious_metal_prices": {
                        "gold": {"price_per_gram": gold_price},
                        "silver": {"price_per_gram": silver_price}
                    },
                    "zakat_due": True,
                    "total_zakat": total_zakat,
                    "currency": currency,
                    "summary": summary,
                    "breakdown": {
                        "assets": formatted_assets,
                        "liabilities": formatted_liabilities,
                        "zakat_by_category": zakat_by_category,
                        "calculations": {
                            "total_assets": total_assets,
                            "total_liabilities": total_liabilities,
                            "net_wealth": net_wealth,
                            "nisab_gold": gold_nisab_value,
                            "nisab_silver": silver_nisab_value,
                            "current_nisab": current_nisab,
                            "total_zakat": total_zakat
                        }
                    }
                }
            else:
                result = {
                    "total_assets": total_assets,
                    "total_liabilities": total_liabilities,
                    "net_wealth": net_wealth,
                    "nisab_threshold": {
                        "gold": gold_nisab_value,
                        "silver": silver_nisab_value,
                        "current": current_nisab
                    },
                    "precious_metal_prices": {
                        "gold": {"price_per_gram": gold_price},
                        "silver": {"price_per_gram": silver_price}
                    },
                    "zakat_due": False,
                    "currency": currency,
                    "summary": summary
                }

            return Response(message=json.dumps(result), break_loop=False)

        except Exception as e:
            message = f"যাকাত গণনায় ত্রুটি: {str(e)}" if language == "bn" else f"Error in zakat calculation: {str(e)}"
            return Response(message=message, break_loop=False)

    def _format_bengali_summary(self, assets, liabilities, zakat_by_category, total_assets, total_liabilities, net_wealth, total_zakat, currency, gold_price, silver_price, gold_nisab_value, silver_nisab_value, current_nisab):
        """Format a detailed summary in Bengali."""
        
        # Nisab and current prices section
        summary = "বিস্তারিত যাকাত হিসাব সংক্ষিপ্তসার:\n\n"
        summary += "নিসাব সীমা এবং বর্তমান মূল্য:\n"
        summary += f"• স্বর্ণের নিসাব: {self.GOLD_NISAB_GRAMS}গ্রাম = {gold_nisab_value:,.2f} {currency}\n"
        summary += f"• রূপার নিসাব: {self.SILVER_NISAB_GRAMS}গ্রাম = {silver_nisab_value:,.2f} {currency}\n"
        summary += f"• বর্তমান নিসাব সীমা: {current_nisab:,.2f} {currency}\n"
        summary += f"• বর্তমান স্বর্ণের মূল্য: {gold_price:,.2f} {currency}/গ্রাম\n"
        summary += f"• বর্তমান রূপার মূল্য: {silver_price:,.2f} {currency}/গ্রাম\n\n"
        
        # Assets section
        summary += "১. প্রদত্ত সম্পদের তথ্য:\n"
        for key, value in assets.items():
            if key in self.ASSET_CATEGORIES:
                rate_key = self.ASSET_CATEGORIES[key]["rate"]
                rate = self.ZAKAT_RATES[rate_key] * 100
                summary += f"   • {self.ASSET_CATEGORIES[key]['bn']}:\n"
                summary += f"     - পরিমাণ: {float(value):,.2f} {currency}\n"
                summary += f"     - যাকাতের হার: {rate}%\n"
        
        # Liabilities section
        if liabilities:
            summary += "\n২. প্রদত্ত দায়ের তথ্য:\n"
            for key, value in liabilities.items():
                bn_key = self.LIABILITIES_CATEGORIES.get(key, key)
                summary += f"   • {bn_key}: {float(value):,.2f} {currency}\n"
        
        # Calculations section
        summary += f"\n৩. হিসাব:\n"
        summary += f"   • মোট সম্পদ: {total_assets:,.2f} {currency}\n"
        summary += f"   • মোট দায়: {total_liabilities:,.2f} {currency}\n"
        summary += f"   • নীট সম্পদ: {net_wealth:,.2f} {currency}\n"
        summary += f"   • নিসাব স্থিতি: {'নিসাব পূর্ণ হয়েছে' if net_wealth >= current_nisab else 'নিসাব পূর্ণ হয়নি'}\n"
        
        # Zakat breakdown
        if net_wealth >= current_nisab:
            summary += "\n৪. যাকাতের বিস্তারিত হিসাব:\n"
            for category, data in zakat_by_category.items():
                summary += f"   • {category}:\n"
                summary += f"     - মূল্য: {data['value']:,.2f} {currency}\n"
                summary += f"     - হার: {data['rate']}%\n"
                summary += f"     - যাকাত: {data['zakat']:,.2f} {currency}\n"
            
            summary += f"\nমোট প্রদেয় যাকাত: {total_zakat:,.2f} {currency}"
            summary += "\n\nবিশেষ নোট:"
            summary += "\n• যাকাত প্রদানের সময় মূল্যের হ্রাস-বৃদ্ধি বিবেচনা করুন"
            summary += "\n• যাকাত বছর (হাওল) পূর্ণ হওয়া নিশ্চিত করুন"
            summary += "\n• সম্পদের মালিকানা ও ঋণমুক্ত অবস্থা যাচাই করুন"
        else:
            summary += "\n৪. যাকাত প্রদান করা ফরয নয়"
            summary += f"\nকারণ: আপনার নীট সম্পদ ({net_wealth:,.2f} {currency}) নিসাব সীমার ({current_nisab:,.2f} {currency}) কম"
            
        return summary

    def _format_english_summary(self, assets, liabilities, zakat_by_category, total_assets, total_liabilities, net_wealth, total_zakat, currency, gold_price, silver_price, gold_nisab_value, silver_nisab_value, current_nisab):
        """Format a detailed summary in English."""
        summary = "Detailed Zakat Calculation Summary:\n\n"
        
        # Nisab and current prices section
        summary += "Nisab and Current Prices:\n"
        summary += f"• Gold Nisab: {self.GOLD_NISAB_GRAMS}g = {gold_nisab_value:,.2f} {currency}\n"
        summary += f"• Silver Nisab: {self.SILVER_NISAB_GRAMS}g = {silver_nisab_value:,.2f} {currency}\n"
        summary += f"• Current Nisab Threshold: {current_nisab:,.2f} {currency}\n"
        summary += f"• Current Gold Price: {gold_price:,.2f} {currency}/g\n"
        summary += f"• Current Silver Price: {silver_price:,.2f} {currency}/g\n\n"
        
        # Assets section
        summary += "1. Provided Assets:\n"
        for key, value in assets.items():
            if key in self.ASSET_CATEGORIES:
                rate_key = self.ASSET_CATEGORIES[key]["rate"]
                rate = self.ZAKAT_RATES[rate_key] * 100
                summary += f"   • {key.replace('_', ' ').title()}:\n"
                summary += f"     - Amount: {float(value):,.2f} {currency}\n"
                summary += f"     - Zakat Rate: {rate}%\n"
        
        # Liabilities section
        if liabilities:
            summary += "\n2. Provided Liabilities:\n"
            for key, value in liabilities.items():
                summary += f"   • {key.replace('_', ' ').title()}: {float(value):,.2f} {currency}\n"
        
        # Calculations section
        summary += f"\n3. Calculations:\n"
        summary += f"   • Total Assets: {total_assets:,.2f} {currency}\n"
        summary += f"   • Total Liabilities: {total_liabilities:,.2f} {currency}\n"
        summary += f"   • Net Wealth: {net_wealth:,.2f} {currency}\n"
        summary += f"   • Nisab Status: {'Meets Nisab' if net_wealth >= current_nisab else 'Below Nisab'}\n"
        
        # Zakat breakdown
        if net_wealth >= current_nisab:
            summary += "\n4. Detailed Zakat Calculation:\n"
            for category, data in zakat_by_category.items():
                en_category = next((k.replace('_', ' ').title() for k, v in self.ASSET_CATEGORIES.items() if v['bn'] == category), category)
                summary += f"   • {en_category}:\n"
                summary += f"     - Value: {data['value']:,.2f} {currency}\n"
                summary += f"     - Rate: {data['rate']}%\n"
                summary += f"     - Zakat: {data['zakat']:,.2f} {currency}\n"
            
            summary += f"\nTotal Zakat Due: {total_zakat:,.2f} {currency}"
            summary += "\n\nImportant Notes:"
            summary += "\n• Consider value fluctuations when paying Zakat"
            summary += "\n• Ensure completion of Zakat year (Hawl)"
            summary += "\n• Verify ownership and debt-free status of assets"
        else:
            summary += "\n4. No Zakat is Due"
            summary += f"\nReason: Your net wealth ({net_wealth:,.2f} {currency}) is below the Nisab threshold ({current_nisab:,.2f} {currency})"
            
        return summary 