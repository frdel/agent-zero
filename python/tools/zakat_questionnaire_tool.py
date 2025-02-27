from ..helpers.tool import Tool, Response

class ZakatQuestionnaireHandler(Tool):
    CONFIG_QUESTIONS = [
        # Currency configuration - commented out for now (Bangladesh-only)
        # {
        #     "id": "currency",
        #     "bn": "আপনার মুদ্রা নির্বাচন করুন:",
        #     "en": "Select your currency:",
        #     "description_bn": "যে মুদ্রায় আপনি হিসাব করতে চান (যেমন: BDT, USD, EUR, GBP, SAR ইত্যাদি)।",
        #     "description_en": "The currency you want to calculate in (e.g., BDT, USD, EUR, GBP, SAR etc.).",
        #     "default": "BDT"
        # },
        {
            "id": "gold_price",
            "bn": "স্বর্ণের বর্তমান মূল্য (প্রতি গ্রাম):",
            "en": "Current Gold Price (per gram):",
            "description_bn": "বর্তমান বাজারে স্বর্ণের প্রতি গ্রামের মূল্য (বাংলাদেশি টাকায়)।",
            "description_en": "Current market price of gold per gram in BDT.",
            "default": "12464"
        },
        {
            "id": "silver_price",
            "bn": "রূপার বর্তমান মূল্য (প্রতি গ্রাম):",
            "en": "Current Silver Price (per gram):",
            "description_bn": "বর্তমান বাজারে রূপার প্রতি গ্রামের মূল্য (বাংলাদেশি টাকায়)।",
            "description_en": "Current market price of silver per gram in BDT.",
            "default": "152"
        }
    ]

    QUESTIONS = [
        # Assets Section
        # 1. Cash and Bank
        {
            "id": "cash_in_hand",
            "bn": "আপনার কাছে থাকা নগদ টাকা:",
            "en": "Cash in Hand:",
            "description_bn": "আপনার নিজের কাছে রাখা নগদ টাকা, যা ব্যাংকে জমা নেই। এর মধ্যে আপনার পকেট, ওয়ালেট, বাড়িতে রাখা টাকা ইত্যাদি অন্তর্ভুক্ত।",
            "description_en": "Cash that you have in your possession, not deposited in banks. This includes money in your pocket, wallet, kept at home, etc.",
            "category": "cash_and_bank"
        },
        {
            "id": "bank_deposits",
            "bn": "ব্যাংকে জমা টাকা (সকল হিসাব):",
            "en": "Bank Deposits (all accounts):",
            "description_bn": "সকল ধরনের ব্যাংক অ্যাকাউন্টে জমা টাকা, যেমন: চলতি হিসাব, সঞ্চয়ী হিসাব, এফডিআর, ডিপিএস ইত্যাদি। মোট টাকার পরিমাণ লিখুন।",
            "description_en": "Money deposited in all types of bank accounts, including: current accounts, savings accounts, fixed deposits (FDR), DPS, etc. Enter the total amount.",
            "category": "cash_and_bank"
        },
        # 2. Loans Given
        {
            "id": "loans_given",
            "bn": "অন্যদের দেওয়া ঋণ:",
            "en": "Cash Given as Loan:",
            "description_bn": "আপনি অন্য কাউকে ধার দিয়েছেন এমন টাকা, যা আপনি ফেরত পাওয়ার আশা করেন। এর মধ্যে বন্ধু-বান্ধব, আত্মীয় বা ব্যবসায়িক ঋণ অন্তর্ভুক্ত।",
            "description_en": "Money you have lent to others that you expect to get back. This includes loans to friends, family, or business loans.",
            "category": "loans_given"
        },
        # 3. Investments
        {
            "id": "shares_investments",
            "bn": "শেয়ার ও বিনিয়োগ:",
            "en": "Shares and Investments:",
            "description_bn": "শেয়ার বাজারে বিনিয়োগ, মিউচুয়াল ফান্ড, বন্ড বা অন্যান্য আর্থিক বিনিয়োগের বর্তমান বাজার মূল্য।",
            "description_en": "Current market value of investments in stock market, mutual funds, bonds, or other financial investments.",
            "category": "investments"
        },
        # 4. Gold and Silver
        {
            "id": "gold_value",
            "bn": "স্বর্ণের মূল্য:",
            "en": "Value of Gold:",
            "description_bn": "আপনার কাছে থাকা সকল স্বর্ণের বর্তমান বাজার মূল্য। এর মধ্যে গহনা, বার, কয়েন ইত্যাদি অন্তর্ভুক্ত।",
            "description_en": "Current market value of all gold in your possession. This includes jewelry, bars, coins, etc.",
            "category": "precious_metals"
        },
        {
            "id": "silver_value",
            "bn": "রূপার মূল্য:",
            "en": "Value of Silver:",
            "description_bn": "আপনার কাছে থাকা সকল রূপার বর্তমান বাজার মূল্য। এর মধ্যে গহনা, বার, কয়েন ইত্যাদি অন্তর্ভুক্ত।",
            "description_en": "Current market value of all silver in your possession. This includes jewelry, bars, coins, etc.",
            "category": "precious_metals"
        },
        # 5. Trade Goods
        {
            "id": "trade_goods",
            "bn": "ব্যবসায়িক পণ্যের মূল্য:",
            "en": "Value of Trade Goods:",
            "description_bn": "ব্যবসার জন্য রাখা সকল পণ্যের বর্তমান বাজার মূল্য। এর মধ্যে স্টক, ইনভেন্টরি, কাঁচামাল ইত্যাদি অন্তর্ভুক্ত।",
            "description_en": "Current market value of all goods kept for business. This includes stock, inventory, raw materials, etc.",
            "category": "trade_goods"
        },
        # 6. Investment Properties
        {
            "id": "investment_properties",
            "bn": "বিনিয়োগ হিসেবে রাখা সম্পত্তির মূল্য:",
            "en": "Property Held as Investments:",
            "description_bn": "বিনিয়োগ হিসেবে রাখা সকল স্থাবর সম্পত্তির বর্তমান বাজার মূল্য। এর মধ্যে ভাড়া দেওয়া বাড়ি, জমি, দোকান ইত্যাদি অন্তর্ভুক্ত। (নিজের বসবাসের বাড়ি অন্তর্ভুক্ত নয়)",
            "description_en": "Current market value of all properties held as investments. This includes rental houses, land, shops, etc. (Excludes your primary residence)",
            "category": "investment_properties"
        },
        # 7. Other Income
        {
            "id": "other_income",
            "bn": "অন্যান্য আয়:",
            "en": "Other Income:",
            "description_bn": "অন্য কোন খাতে প্রাপ্ত আয় যা উপরের কোন বিভাগে অন্তর্ভুক্ত হয়নি। যেমন: রয়্যালটি, কমিশন, পুরস্কার ইত্যাদি।",
            "description_en": "Any other income not included in above categories. For example: royalties, commissions, prizes, etc.",
            "category": "other_income"
        },
        # Liabilities Section
        # 1. Debts
        {
            "id": "borrowed_money",
            "bn": "ধার করা টাকা বা বাকিতে কেনা পণ্যের মূল্য:",
            "en": "Debts (Borrowed Money or Goods Brought on Credit):",
            "description_bn": "আপনি অন্যের কাছ থেকে ধার নিয়েছেন এমন টাকা বা বাকিতে কেনা পণ্যের মূল্য। এর মধ্যে ব্যক্তিগত ঋণ, ব্যাংক লোন, ক্রেডিট কার্ড বাকি ইত্যাদি অন্তর্ভুক্ত।",
            "description_en": "Money you have borrowed or value of goods bought on credit. This includes personal loans, bank loans, credit card dues, etc.",
            "category": "liabilities"
        },
        # 2. Dues
        {
            "id": "dues",
            "bn": "বাকি বিল, পেমেন্ট বা বেতন:",
            "en": "Dues (Bills, Payments or Salaries):",
            "description_bn": "আপনার উপর বাকি থাকা বিল, পেমেন্ট বা বেতন। যেমন: ইউটিলিটি বিল, ভাড়া, কর্মচারীদের বেতন ইত্যাদি।",
            "description_en": "Outstanding bills, payments, or salaries you owe. For example: utility bills, rent, employee salaries, etc.",
            "category": "liabilities"
        },
        # 3. Expenses
        {
            "id": "expenses",
            "bn": "বাদ দিন আপনার খরচ:",
            "en": "Deduct Your Expenses:",
            "description_bn": "আপনার নিত্য প্রয়োজনীয় খরচ যা আগামী একমাসে প্রয়োজন হবে। যেমন: খাবার, যাতায়াত, চিকিৎসা ইত্যাদি।",
            "description_en": "Your necessary expenses for the next month. For example: food, transportation, medical expenses, etc.",
            "category": "liabilities"
        }
    ]

    async def execute(self, current_question=0, answers=None, language="bn", calculation_date=None, **kwargs):
        """Handle the questionnaire flow for Zakat calculation.
        
        Args:
            current_question (int): Current question index
            answers (dict): Previously collected answers
            language (str): Language preference ('bn' for Bengali, 'en' for English)
            calculation_date (datetime): Specific date for calculation (optional)
        """
        try:
            if answers is None:
                answers = {}

            # Handle configuration questions first
            if current_question < len(self.CONFIG_QUESTIONS):
                config_question = self.CONFIG_QUESTIONS[current_question]
                
                # Format the configuration question prompt
                if language == "bn":
                    question_text = f"""যাকাত হিসাব কনফিগারেশন:

প্রশ্ন {current_question + 1} / {len(self.CONFIG_QUESTIONS)}:

{config_question['bn']}

{config_question['description_bn']}

ডিফল্ট মান: {config_question['default']}"""
                else:
                    question_text = f"""Zakat Calculation Configuration:

Question {current_question + 1} of {len(self.CONFIG_QUESTIONS)}:

{config_question['en']}

{config_question['description_en']}

Default value: {config_question['default']}"""
                
                response = {
                    "status": "config_question",
                    "question_id": config_question["id"],
                    "prompt": question_text,
                    "current_question": current_question + 1,
                    "total_config_questions": len(self.CONFIG_QUESTIONS),
                    "answers_so_far": answers,
                    "language": language,
                    "default": config_question["default"]
                }
                
                return Response(
                    message=str(response),
                    break_loop=False
                )

            # Adjust the question index for main questions
            main_question_index = current_question - len(self.CONFIG_QUESTIONS)

            # If we've collected all answers, calculate Zakat
            if main_question_index >= len(self.QUESTIONS):
                # Separate assets and liabilities
                assets = {}
                liabilities = {}
                
                # Get configuration values - using fixed BDT for now
                currency = "BDT"  # Fixed for Bangladesh
                gold_price = float(answers.get("gold_price", 12464))
                silver_price = float(answers.get("silver_price", 152))
                
                # Process answers by category
                for k, v in answers.items():
                    if k not in ["gold_price", "silver_price"] and v and float(v) > 0:  # Removed currency check
                        question = next((q for q in self.QUESTIONS if q["id"] == k), None)
                        if question:
                            category = question.get("category", "")
                            if category in ["liabilities"]:
                                liabilities[k] = v
                            else:
                                assets[k] = v
                
                if not assets:
                    return Response(
                        message=str({
                            "status": "error",
                            "message": "কোন সম্পদের তথ্য প্রদান করা হয়নি।" if language == "bn" else "No assets information provided.",
                            "current_question": len(self.CONFIG_QUESTIONS),
                            "language": language
                        }),
                        break_loop=False
                    )

                # Use Zakat calculator tool with collected answers
                return Response(
                    message=str({
                        "status": "complete",
                        "use_tool": "zakat_calculator_tool",
                        "tool_args": {
                            "assets": assets,
                            "liabilities": liabilities if liabilities else None,
                            "currency": currency,
                            "language": language,
                            "gold_price": gold_price,
                            "silver_price": silver_price,
                            "calculation_date": calculation_date
                        }
                    }),
                    break_loop=False
                )

            # Get current main question
            question = self.QUESTIONS[main_question_index]
            
            # Format the question prompt
            if language == "bn":
                question_text = f"""যাকাত হিসাব প্রশ্নমালা:

প্রশ্ন {main_question_index + 1} / {len(self.QUESTIONS)}:

{question['bn']}

{question['description_bn']}"""
            else:
                question_text = f"""Zakat calculation questionnaire:

Question {main_question_index + 1} of {len(self.QUESTIONS)}:

{question['en']}

{question['description_en']}"""
            
            # Add options if available
            response = {
                "status": "question",
                "question_id": question["id"],
                "prompt": question_text,
                "current_question": current_question + 1,
                "total_questions": len(self.CONFIG_QUESTIONS) + len(self.QUESTIONS),
                "answers_so_far": answers,
                "language": language
            }
            
            if "options" in question:
                response["options"] = question["options"]

            return Response(
                message=str(response),
                break_loop=False
            )

        except Exception as e:
            error_msg = "ত্রুটি ঘটেছে: " if language == "bn" else "Error occurred: "
            return Response(
                message=str({
                    "status": "error",
                    "message": f"{error_msg}{str(e)}",
                    "current_question": current_question,
                    "language": language
                }),
                break_loop=False
            ) 