# Mathematical and Currency Formatting Guidelines

## Brazilian Currency (Real) - CRITICAL RULE
- ALWAYS use: "$ 100,50" (only dollar sign, NO R)
- NEVER use: "R$ 100,50", "R\ 100,50" or "R\100,50"
- The R letter conflicts with LaTeX mathematical expressions
- Examples:
  - ✅ "Preço: $ 8,00"
  - ❌ "Preço: R$ 8,00"
  - ❌ "Preço: R\ 8,00"

## Mathematical Expressions
- Wrap ALL LaTeX math in $ delimiters
- Use only numbers inside fractions, NO currency symbols
- Examples:
  - ✅ "Cálculo: $\frac{5,00}{1,265}$ = $ 3,95"
  - ❌ "Cálculo: \frac{R$ 5,00}{1,265} = R$ 3,95"

## Mathematical Symbols
- Multiplication: ALWAYS use $\times$ not \times
- Fractions: $\frac{a}{b}$ not \frac{a}{b}
- Bold in math: $\textbf{text}$ not \textbf{text}

## CRITICAL: Examples with Currency
- ✅ "$ 1,00 $\times$ 26,5% = $ 0,265"
- ❌ "R$ 1,00 \times 26,5% = R$ 0,265"
- ✅ "Imposto: $ 8,00 - $\frac{8,00}{1,265}$ = $ 6,32"
- ❌ "Imposto: R$ 8,00 - \frac{R$ 8,00}{1,265} = R$ 6,32"

## Complete Example
"Crédito: $ 1,00 $\times$ 26,5% = $ 0,265
Imposto: $ 8,00 - $\frac{8,00}{1,265}$ = $ 6,32"