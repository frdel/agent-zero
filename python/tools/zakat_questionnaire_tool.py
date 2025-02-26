from ..helpers.tool import Tool, Response

class ZakatQuestionnaireHandler(Tool):
    QUESTIONS = [
        # Assets Section
        # 1. Cash and Bank
        {
            "id": "cash_in_hand",
            "bn": "আপনার কাছে থাকা নগদ টাকা:",
            "en": "Cash in Hand:",
            "category": "cash_and_bank"
        },
        {
            "id": "bank_deposits",
            "bn": "ব্যাংকে জমা টাকা (সকল হিসাব):",
            "en": "Bank Deposits (all accounts):",
            "category": "cash_and_bank"
        },
        # 2. Loans Given
        {
            "id": "loans_given",
            "bn": "অন্যদের দেওয়া ঋণ:",
            "en": "Cash Given as Loan:",
            "category": "loans_given"
        },
        # 3. Investments
        {
            "id": "shares_investments",
            "bn": "শেয়ার ও বিনিয়োগ:",
            "en": "Shares and Investments:",
            "category": "investments"
        },
        # 4. Gold and Silver
        {
            "id": "gold_value",
            "bn": "স্বর্ণের মূল্য:",
            "en": "Value of Gold:",
            "category": "precious_metals"
        },
        {
            "id": "silver_value",
            "bn": "রূপার মূল্য:",
            "en": "Value of Silver:",
            "category": "precious_metals"
        },
        # 5. Trade Goods
        {
            "id": "trade_goods",
            "bn": "ব্যবসায়িক পণ্যের মূল্য:",
            "en": "Value of Trade Goods:",
            "category": "trade_goods"
        },
        # 6. Investment Properties
        {
            "id": "investment_properties",
            "bn": "বিনিয়োগ হিসেবে রাখা সম্পত্তির মূল্য:",
            "en": "Property Held as Investments:",
            "category": "investment_properties"
        },
        # 7. Other Income
        {
            "id": "other_income",
            "bn": "অন্যান্য আয়:",
            "en": "Other Income Price:",
            "category": "other_income"
        },
        # Liabilities Section
        # 1. Debts
        {
            "id": "borrowed_money",
            "bn": "ধার করা টাকা বা বাকিতে কেনা পণ্যের মূল্য:",
            "en": "Debts (Borrowed Money or Goods Brought on Credit):",
            "category": "liabilities"
        },
        # 2. Dues
        {
            "id": "dues",
            "bn": "বাকি বিল, পেমেন্ট বা বেতন:",
            "en": "Dues (Bills, Payments or Salaries):",
            "category": "liabilities"
        },
        # 3. Expenses
        {
            "id": "expenses",
            "bn": "বাদ দিন আপনার খরচ:",
            "en": "Deduct Your Expenses:",
            "category": "liabilities"
        }
    ]

    async def execute(self, current_question=0, answers=None, **kwargs):
        """Handle the questionnaire flow for Zakat calculation."""
        try:
            if answers is None:
                answers = {}

            # If we've collected all answers, calculate Zakat
            if current_question >= len(self.QUESTIONS):
                # Separate assets and liabilities
                assets = {}
                liabilities = {}
                
                # Process answers by category
                for k, v in answers.items():
                    if v and float(v) > 0:
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
                            "message": "কোন সম্পদের তথ্য প্রদান করা হয়নি।",
                            "current_question": 0
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
                            "currency": "BDT"
                        }
                    }),
                    break_loop=False
                )

            # Get current question
            question = self.QUESTIONS[current_question]
            
            # Add options if available
            response = {
                "status": "question",
                "question_id": question["id"],
                "question_bn": question["bn"],
                "question_en": question["en"],
                "current_question": current_question,
                "total_questions": len(self.QUESTIONS),
                "answers_so_far": answers
            }
            
            if "options" in question:
                response["options"] = question["options"]

            return Response(
                message=str(response),
                break_loop=False
            )

        except Exception as e:
            return Response(
                message=str({
                    "status": "error",
                    "message": f"ত্রুটি ঘটেছে: {str(e)}",
                    "current_question": current_question
                }),
                break_loop=False
            ) 