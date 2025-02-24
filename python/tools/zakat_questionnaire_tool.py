from ..helpers.tool import Tool, Response

class ZakatQuestionnaireHandler(Tool):
    QUESTIONS = [
        {
            "id": "gold_price",
            "bn": "বর্তমানে প্রতি গ্রাম স্বর্ণের মূল্য কত? (টাকায়)",
            "en": "What is the current gold price per gram? (in BDT)"
        },
        {
            "id": "savings",
            "bn": "আপনার মোট নগদ অর্থ ও ব্যাংক সঞ্চয় কত? (টাকায়)",
            "en": "What is your total cash and bank savings? (in BDT)"
        },
        {
            "id": "gold_jewelry",
            "bn": "আপনার কাছে থাকা স্বর্ণালংকারের বর্তমান মূল্য কত? (টাকায়)",
            "en": "What is the current value of your gold jewelry? (in BDT)"
        },
        {
            "id": "silver",
            "bn": "আপনার কাছে থাকা রূপার বর্তমান মূল্য কত? (টাকায়)",
            "en": "What is the current value of your silver? (in BDT)"
        },
        {
            "id": "investments",
            "bn": "আপনার মোট বিনিয়োগের পরিমাণ কত? (শেয়ার, মিউচুয়াল ফান্ড ইত্যাদি) (টাকায়)",
            "en": "What is your total investments? (stocks, mutual funds etc.) (in BDT)"
        },
        {
            "id": "business_goods",
            "bn": "আপনার ব্যবসায়িক পণ্যের মোট মূল্য কত? (টাকায়)",
            "en": "What is the total value of your business inventory? (in BDT)"
        },
        {
            "id": "rental_income",
            "bn": "বিগত এক বছরে ভাড়া থেকে প্রাপ্ত মোট আয় কত? (টাকায়)",
            "en": "What is your total rental income for the past year? (in BDT)"
        },
        {
            "id": "fixed_deposits",
            "bn": "আপনার স্থায়ী আমানতের (FDR) মোট পরিমাণ কত? (টাকায়)",
            "en": "What is your total fixed deposits (FDR)? (in BDT)"
        },
        {
            "id": "receivables",
            "bn": "অন্যের কাছ থেকে পাওনা মোট অর্থের পরিমাণ কত? (টাকায়)",
            "en": "What is the total amount others owe you? (in BDT)"
        }
    ]

    async def execute(self, current_question=0, answers=None, **kwargs):
        """Handle the questionnaire flow for Zakat calculation."""
        try:
            if answers is None:
                answers = {}

            # If we've collected all answers, calculate Zakat
            if current_question >= len(self.QUESTIONS):
                # Filter out empty or zero values
                filtered_assets = {
                    k: v for k, v in answers.items() 
                    if k != "gold_price" and v and float(v) > 0
                }
                
                if not filtered_assets:
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
                            "assets": filtered_assets,
                            "gold_price": answers.get("gold_price", "0"),
                            "currency": "BDT"
                        }
                    }),
                    break_loop=False
                )

            # Get current question
            question = self.QUESTIONS[current_question]
            
            return Response(
                message=str({
                    "status": "question",
                    "question_id": question["id"],
                    "question_bn": question["bn"],
                    "question_en": question["en"],
                    "current_question": current_question,
                    "total_questions": len(self.QUESTIONS),
                    "answers_so_far": answers
                }),
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