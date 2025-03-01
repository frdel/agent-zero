from ..helpers.tool import Tool, Response
import json

class ZakatQuestionnaireHandler(Tool):
    # Unified question list with categories
    QUESTIONS = [
        # Configuration Section
        {
            "id": "gold_price",
            "bn": "স্বর্ণের বর্তমান মূল্য (প্রতি গ্রাম):",
            "en": "Current Gold Price (per gram):",
            "description_bn": "বর্তমান বাজারে স্বর্ণের প্রতি গ্রামের মূল্য (বাংলাদেশি টাকায়)।",
            "description_en": "Current market price of gold per gram in BDT.",
            "default": "12464",
            "category": "configuration",
            "sequence": 0
        },
        {
            "id": "silver_price",
            "bn": "রূপার বর্তমান মূল্য (প্রতি গ্রাম):",
            "en": "Current Silver Price (per gram):",
            "description_bn": "বর্তমান বাজারে রূপার প্রতি গ্রামের মূল্য (বাংলাদেশি টাকায়)।",
            "description_en": "Current market price of silver per gram in BDT.",
            "default": "152",
            "category": "configuration",
            "sequence": 1
        },
        
        # Assets Section
        # 1. Cash and Bank
        {
            "id": "cash_in_hand",
            "bn": "আপনার কাছে থাকা নগদ টাকা:",
            "en": "Cash in Hand:",
            "description_bn": "আপনার নিজের কাছে রাখা নগদ টাকা, যা ব্যাংকে জমা নেই। এর মধ্যে আপনার পকেট, ওয়ালেট, বাড়িতে রাখা টাকা ইত্যাদি অন্তর্ভুক্ত।",
            "description_en": "Cash that you have in your possession, not deposited in banks. This includes money in your pocket, wallet, kept at home, etc.",
            "category": "cash_and_bank",
            "sequence": 2
        },
        {
            "id": "bank_deposits",
            "bn": "ব্যাংকে জমা টাকা (সকল হিসাব):",
            "en": "Bank Deposits (all accounts):",
            "description_bn": "সকল ধরনের ব্যাংক অ্যাকাউন্টে জমা টাকা, যেমন: চলতি হিসাব, সঞ্চয়ী হিসাব, এফডিআর, ডিপিএস ইত্যাদি। মোট টাকার পরিমাণ লিখুন।",
            "description_en": "Money deposited in all types of bank accounts, including: current accounts, savings accounts, fixed deposits (FDR), DPS, etc. Enter the total amount.",
            "category": "cash_and_bank",
            "sequence": 3
        },
        # 2. Loans Given
        {
            "id": "loans_given",
            "bn": "অন্যদের দেওয়া ঋণ:",
            "en": "Cash Given as Loan:",
            "description_bn": "আপনি অন্য কাউকে ধার দিয়েছেন এমন টাকা, যা আপনি ফেরত পাওয়ার আশা করেন। এর মধ্যে বন্ধু-বান্ধব, আত্মীয় বা ব্যবসায়িক ঋণ অন্তর্ভুক্ত।",
            "description_en": "Money you have lent to others that you expect to get back. This includes loans to friends, family, or business loans.",
            "category": "loans_given",
            "sequence": 4
        },
        # 3. Investments
        {
            "id": "shares_investments",
            "bn": "শেয়ার ও বিনিয়োগ:",
            "en": "Shares and Investments:",
            "description_bn": "শেয়ার বাজারে বিনিয়োগ, মিউচুয়াল ফান্ড, বন্ড বা অন্যান্য আর্থিক বিনিয়োগের বর্তমান বাজার মূল্য।",
            "description_en": "Current market value of investments in stock market, mutual funds, bonds, or other financial investments.",
            "category": "investments",
            "sequence": 5
        },
        # 4. Gold and Silver
        {
            "id": "gold_input_type",
            "bn": "স্বর্ণের তথ্য কীভাবে দিতে চান?",
            "en": "How would you like to provide gold information?",
            "description_bn": "আপনি কি স্বর্ণের ওজন নাকি মূল্য দিতে চান? ওজন হলে গ্রাম হিসেবে, মূল্য হলে টাকায়।",
            "description_en": "Would you like to provide gold by weight or value? Weight in grams, value in BDT.",
            "options_bn": ["ওজন (গ্রাম)", "মূল্য (টাকা)"],
            "options_en": ["Weight (grams)", "Value (BDT)"],
            "category": "precious_metals",
            "sequence": 6
        },
        {
            "id": "gold_weight",
            "bn": "স্বর্ণের ওজন (গ্রাম):",
            "en": "Gold Weight (grams):",
            "description_bn": "আপনার কাছে থাকা সকল স্বর্ণের মোট ওজন গ্রাম হিসেবে। এর মধ্যে গহনা, বার, কয়েন ইত্যাদি অন্তর্ভুক্ত।",
            "description_en": "Total weight of all gold in your possession in grams. This includes jewelry, bars, coins, etc.",
            "category": "precious_metals",
            "condition": {"id": "gold_input_type", "value": "0"},
            "sequence": 7
        },
        {
            "id": "gold_value",
            "bn": "স্বর্ণের মূল্য (টাকা):",
            "en": "Value of Gold (BDT):",
            "description_bn": "আপনার কাছে থাকা সকল স্বর্ণের বর্তমান বাজার মূল্য। এর মধ্যে গহনা, বার, কয়েন ইত্যাদি অন্তর্ভুক্ত।",
            "description_en": "Current market value of all gold in your possession. This includes jewelry, bars, coins, etc.",
            "category": "precious_metals",
            "condition": {"id": "gold_input_type", "value": "1"},
            "sequence": 8
        },
        {
            "id": "silver_input_type",
            "bn": "রূপার তথ্য কীভাবে দিতে চান?",
            "en": "How would you like to provide silver information?",
            "description_bn": "আপনি কি রূপার ওজন নাকি মূল্য দিতে চান? ওজন হলে গ্রাম হিসেবে, মূল্য হলে টাকায়।",
            "description_en": "Would you like to provide silver by weight or value? Weight in grams, value in BDT.",
            "options_bn": ["ওজন (গ্রাম)", "মূল্য (টাকা)"],
            "options_en": ["Weight (grams)", "Value (BDT)"],
            "category": "precious_metals",
            "sequence": 9
        },
        {
            "id": "silver_weight",
            "bn": "রূপার ওজন (গ্রাম):",
            "en": "Silver Weight (grams):",
            "description_bn": "আপনার কাছে থাকা সকল রূপার মোট ওজন গ্রাম হিসেবে। এর মধ্যে গহনা, বার, কয়েন ইত্যাদি অন্তর্ভুক্ত।",
            "description_en": "Total weight of all silver in your possession in grams. This includes jewelry, bars, coins, etc.",
            "category": "precious_metals",
            "condition": {"id": "silver_input_type", "value": "0"},
            "sequence": 10
        },
        {
            "id": "silver_value",
            "bn": "রূপার মূল্য (টাকা):",
            "en": "Value of Silver (BDT):",
            "description_bn": "আপনার কাছে থাকা সকল রূপার বর্তমান বাজার মূল্য। এর মধ্যে গহনা, বার, কয়েন ইত্যাদি অন্তর্ভুক্ত।",
            "description_en": "Current market value of all silver in your possession. This includes jewelry, bars, coins, etc.",
            "category": "precious_metals",
            "condition": {"id": "silver_input_type", "value": "1"},
            "sequence": 11
        },
        # 5. Trade Goods
        {
            "id": "trade_goods",
            "bn": "ব্যবসায়িক পণ্যের মূল্য:",
            "en": "Value of Trade Goods:",
            "description_bn": "ব্যবসার জন্য রাখা সকল পণ্যের বর্তমান বাজার মূল্য। এর মধ্যে স্টক, ইনভেন্টরি, কাঁচামাল ইত্যাদি অন্তর্ভুক্ত।",
            "description_en": "Current market value of all goods kept for business. This includes stock, inventory, raw materials, etc.",
            "category": "trade_goods",
            "sequence": 12
        },
        # 6. Agricultural Assets
        {
            "id": "has_agricultural_assets",
            "bn": "আপনার কি কৃষি সম্পদ আছে?",
            "en": "Do you have agricultural assets?",
            "description_bn": "আপনার কি কোন কৃষি সম্পদ আছে, যেমন: ফসল বা বাগান থেকে উৎপাদিত পণ্য?",
            "description_en": "Do you have any agricultural assets, such as crops or produce from farms/gardens?",
            "options_bn": ["হ্যাঁ", "না"],
            "options_en": ["Yes", "No"],
            "category": "agricultural",
            "sequence": 13
        },
        {
            "id": "irrigated_crops",
            "bn": "সেচকৃত ফসলের মূল্য:",
            "en": "Value of Irrigated Crops:",
            "description_bn": "যে ফসল উৎপাদনে কৃত্রিম সেচ ব্যবহার করা হয়েছে তার মূল্য। এর উপর যাকাতের হার ৫%।",
            "description_en": "Value of crops produced using artificial irrigation. Zakat rate on this is 5%.",
            "category": "agricultural",
            "condition": {"id": "has_agricultural_assets", "value": "0"},
            "sequence": 14
        },
        {
            "id": "rain_fed_crops",
            "bn": "বৃষ্টি নির্ভর ফসলের মূল্য:",
            "en": "Value of Rain-fed Crops:",
            "description_bn": "যে ফসল উৎপাদনে শুধুমাত্র বৃষ্টির পানি ব্যবহার করা হয়েছে তার মূল্য। এর উপর যাকাতের হার ১০%।",
            "description_en": "Value of crops that rely solely on rainwater. Zakat rate on this is 10%.",
            "category": "agricultural",
            "condition": {"id": "has_agricultural_assets", "value": "0"},
            "sequence": 15
        },
        # 7. Mining Resources
        {
            "id": "has_mining_resources",
            "bn": "আপনার কি খনিজ সম্পদ আছে?",
            "en": "Do you have mining resources?",
            "description_bn": "আপনার কি কোন খনিজ সম্পদ আছে, যেমন: জমি থেকে উত্তোলিত খনিজ দ্রব্য?",
            "description_en": "Do you have any mining resources, such as minerals extracted from the earth?",
            "options_bn": ["হ্যাঁ", "না"],
            "options_en": ["Yes", "No"],
            "category": "mining",
            "sequence": 16
        },
        {
            "id": "mining_resources",
            "bn": "খনিজ সম্পদের মূল্য:",
            "en": "Value of Mining Resources:",
            "description_bn": "জমি থেকে উত্তোলিত খনিজ সম্পদের মূল্য। এর উপর যাকাতের হার ২০%।",
            "description_en": "Value of mining resources extracted from the earth. Zakat rate on this is 20%.",
            "category": "mining",
            "condition": {"id": "has_mining_resources", "value": "0"},
            "sequence": 17
        },
        # 8. Investment Properties
        {
            "id": "investment_properties",
            "bn": "বিনিয়োগ হিসেবে রাখা সম্পত্তির মূল্য:",
            "en": "Property Held as Investments:",
            "description_bn": "বিনিয়োগ হিসেবে রাখা সকল স্থাবর সম্পত্তির বর্তমান বাজার মূল্য। এর মধ্যে ভাড়া দেওয়া বাড়ি, জমি, দোকান ইত্যাদি অন্তর্ভুক্ত। (নিজের বসবাসের বাড়ি অন্তর্ভুক্ত নয়)",
            "description_en": "Current market value of all properties held as investments. This includes rental houses, land, shops, etc. (Excludes your primary residence)",
            "category": "investment_properties",
            "sequence": 18
        },
        # 9. Other Income
        {
            "id": "other_income",
            "bn": "অন্যান্য আয়:",
            "en": "Other Income:",
            "description_bn": "অন্য কোন খাতে প্রাপ্ত আয় যা উপরের কোন বিভাগে অন্তর্ভুক্ত হয়নি। যেমন: রয়্যালটি, কমিশন, পুরস্কার ইত্যাদি।",
            "description_en": "Any other income not included in above categories. For example: royalties, commissions, prizes, etc.",
            "category": "other_income",
            "sequence": 19
        },
        # Liabilities Section
        # 1. Debts
        {
            "id": "borrowed_money",
            "bn": "ধার করা টাকা বা বাকিতে কেনা পণ্যের মূল্য:",
            "en": "Debts (Borrowed Money or Goods Brought on Credit):",
            "description_bn": "আপনি অন্যের কাছ থেকে ধার নিয়েছেন এমন টাকা বা বাকিতে কেনা পণ্যের মূল্য। এর মধ্যে ব্যক্তিগত ঋণ, ব্যাংক লোন, ক্রেডিট কার্ড বাকি ইত্যাদি অন্তর্ভুক্ত।",
            "description_en": "Money you have borrowed or value of goods bought on credit. This includes personal loans, bank loans, credit card dues, etc.",
            "category": "liabilities",
            "sequence": 20
        },
        # 2. Dues
        {
            "id": "dues",
            "bn": "বাকি বিল, পেমেন্ট বা বেতন:",
            "en": "Dues (Bills, Payments or Salaries):",
            "description_bn": "আপনার উপর বাকি থাকা বিল, পেমেন্ট বা বেতন। যেমন: ইউটিলিটি বিল, ভাড়া, কর্মচারীদের বেতন ইত্যাদি।",
            "description_en": "Outstanding bills, payments, or salaries you owe. For example: utility bills, rent, employee salaries, etc.",
            "category": "liabilities",
            "sequence": 21
        },
        # 3. Expenses
        {
            "id": "expenses",
            "bn": "বাদ দিন আপনার খরচ:",
            "en": "Deduct Your Expenses:",
            "description_bn": "আপনার নিত্য প্রয়োজনীয় খরচ যা আগামী একমাসে প্রয়োজন হবে। যেমন: খাবার, যাতায়াত, চিকিৎসা ইত্যাদি।",
            "description_en": "Your necessary expenses for the next month. For example: food, transportation, medical expenses, etc.",
            "category": "liabilities",
            "sequence": 22
        }
    ]

    # Get questions by category for easy reference
    def get_questions_by_category(self, category):
        return [q for q in self.QUESTIONS if q.get("category") == category]

    # Find the next unanswered question
    def get_next_question(self, answers):
        # Sort questions by sequence
        sorted_questions = sorted(self.QUESTIONS, key=lambda q: q["sequence"])
        
        # Find the first question that hasn't been answered yet
        for question in sorted_questions:
            # Skip questions with conditions that aren't met
            if "condition" in question:
                condition = question["condition"]
                condition_id = condition["id"]
                condition_value = condition["value"]
                
                # Skip if the condition question isn't answered yet
                if condition_id not in answers:
                    continue
                    
                # Skip if the condition isn't met
                if answers[condition_id] != condition_value:
                    continue
            
            if question["id"] not in answers:
                return question
                
        # If all questions have been answered, return None
        return None

    async def execute(self, current_question=None, answers=None, language="bn", calculation_date=None, **kwargs):
        """Handle the questionnaire flow for Zakat calculation.
        
        Args:
            current_question (int): DEPRECATED - No longer used but kept for backward compatibility
            answers (dict): Previously collected answers
            language (str): Language preference ('bn' for Bengali, 'en' for English)
            calculation_date (datetime): Specific date for calculation (optional)
        """
        try:
            if answers is None:
                answers = {}
                
            # Find the next question to ask based on answers already provided
            next_question = self.get_next_question(answers)
            
            # If all questions have been answered, proceed to calculation
            if next_question is None:
                # Separate assets and liabilities
                assets = {}
                liabilities = {}
                
                # Get configuration values
                currency = "BDT"  # Fixed for Bangladesh
                gold_price = float(answers.get("gold_price", 12464))
                silver_price = float(answers.get("silver_price", 152))
                
                # Process answers by category
                for k, v in answers.items():
                    # Skip input type selection questions
                    if k in ["gold_input_type", "silver_input_type", "has_agricultural_assets", "has_mining_resources"]:
                        continue
                        
                    if k not in ["gold_price", "silver_price"] and v and float(v) > 0:
                        question = next((q for q in self.QUESTIONS if q["id"] == k), None)
                        if question:
                            category = question.get("category", "")
                            if category == "liabilities":
                                liabilities[k] = v
                            elif category != "configuration":  # Skip configuration values
                                assets[k] = v
                
                if not assets:
                    error_message = "কোন সম্পদের তথ্য প্রদান করা হয়নি।" if language == "bn" else "No assets information provided."
                    
                    # Response for error - directly return the error message to show to user
                    return Response(
                        message=error_message,
                        break_loop=True  # Break the loop on error
                    )

                # Data for the Zakat calculator
                calculator_args = {
                    "assets": assets,
                    "liabilities": liabilities if liabilities else None,
                    "currency": currency,
                    "language": language,
                    "gold_price": gold_price,
                    "silver_price": silver_price,
                    "calculation_date": calculation_date
                }
                
                completion_message = "যাকাত গণনা সম্পন্ন। ফলাফলে এগিয়ে যাচ্ছি।" if language == "bn" else "Zakat calculation complete. Proceeding to results."
                
                # Return a simple dictionary with the command to use the calculator tool
                return Response(
                    message={
                        "message_to_user": completion_message,
                        "status": "complete",
                        "use_tool": "zakat_calculator_tool",
                        "tool_args": calculator_args
                    },
                    break_loop=True  # Break the loop when complete
                )

            # Get the current category and count questions in this category
            current_category = next_question.get("category", "")
            category_questions = self.get_questions_by_category(current_category)
            category_index = category_questions.index(next_question) + 1
            
            # Format the question prompt with category header
            category_headers = {
                "configuration": "যাকাত হিসাব কনফিগারেশন" if language == "bn" else "Zakat Calculation Configuration",
                "cash_and_bank": "নগদ ও ব্যাংক" if language == "bn" else "Cash and Bank",
                "loans_given": "প্রদত্ত ঋণ" if language == "bn" else "Loans Given",
                "investments": "বিনিয়োগ" if language == "bn" else "Investments",
                "precious_metals": "মূল্যবান ধাতু" if language == "bn" else "Precious Metals",
                "trade_goods": "ব্যবসায়িক পণ্য" if language == "bn" else "Trade Goods",
                "agricultural": "কৃষি সম্পদ" if language == "bn" else "Agricultural Assets",
                "mining": "খনিজ সম্পদ" if language == "bn" else "Mining Resources",
                "investment_properties": "বিনিয়োগকৃত সম্পত্তি" if language == "bn" else "Investment Properties",
                "other_income": "অন্যান্য আয়" if language == "bn" else "Other Income",
                "liabilities": "দায়" if language == "bn" else "Liabilities"
            }
            
            category_header = category_headers.get(current_category, "")
            
            # Get question index for display (1-indexed)
            question_index = next_question["sequence"] + 1
            
            question_text = ""
            response_type = "text"
            options = []  # Initialize options with an empty list
            
            # Format question based on type
            if "options_bn" in next_question or "options_en" in next_question:
                # This is a multiple choice question
                response_type = "multiple_choice"
                
                if language == "bn":
                    question_text = f"""যাকাত হিসাব প্রশ্নমালা: {category_header}
প্রশ্ন {question_index} / {len(self.QUESTIONS)}:
{next_question['bn']} {next_question['description_bn']}"""
                    options = next_question.get("options_bn", [])
                else:
                    question_text = f"""Zakat calculation questionnaire: {category_header}
Question {question_index} of {len(self.QUESTIONS)}:
{next_question['en']} {next_question['description_en']}"""
                    options = next_question.get("options_en", [])
            else:
                # This is a text input question
                if language == "bn":
                    question_text = f"""যাকাত হিসাব প্রশ্নমালা: {category_header}
প্রশ্ন {question_index} / {len(self.QUESTIONS)}:
{next_question['bn']} {next_question['description_bn']}"""
                    input_prompt = "\n\nদয়া করে আপনার উত্তর লিখুন:"
                else:
                    question_text = f"""Zakat calculation questionnaire: {category_header}
Question {question_index} of {len(self.QUESTIONS)}:
{next_question['en']} {next_question['description_en']}"""
                    input_prompt = "\n\nPlease enter your answer:"

                # Add default value for configuration questions
                if "default" in next_question:
                    if language == "bn":
                        question_text += f"\nডিফল্ট মান: {next_question['default']}"
                    else:
                        question_text += f"\nDefault value: {next_question['default']}"
                
                # Add input prompt
                question_text += input_prompt
            
            # Prepare response data
            response_data = {
                "text": question_text,
                "type": response_type,
                "question_id": next_question["id"]
            }
            
            # Add options for multiple choice questions
            if response_type == "multiple_choice":
                response_data["options"] = options
            
            # Return formatted question data
            return Response(
                message=response_data,
                break_loop=True  # Break the loop to wait for user input
            )

        except Exception as e:
            error_msg = f"{'ত্রুটি ঘটেছে:' if language == 'bn' else 'Error occurred:'} {str(e)}"
            
            # Return the error message directly to show to user
            return Response(
                message=error_msg,
                break_loop=True  # Break the loop on error
            ) 