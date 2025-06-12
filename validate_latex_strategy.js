// VALIDAÇÃO DA ESTRATÉGIA ROBUSTA DE CORREÇÃO LATEX
// Script de teste puro JavaScript (Node.js)

const latexCorrections = [
  {
    pattern: /(?<!\\)\brac\s*\{([^}]*)\}\s*\{([^}]*)\}/g,
    replacement: '\\frac{$1}{$2}',
    needsDelimiters: true,
    priority: 1,
    description: 'Corrige rac{}{} para \\frac{}{}'
  },
  {
    pattern: /(?<!\\)\bextbf\s*\{([^}]*)\}/g,
    replacement: '**$1**',
    needsDelimiters: false,
    priority: 2,
    description: 'Converte extbf{} para **bold**'
  },
  {
    pattern: /(?<!\\)\bimes\s*([0-9]+(?:[,\.][0-9]+)*)/g,
    replacement: '\\times $1',
    needsDelimiters: true,
    priority: 3,
    description: 'Corrige imes + números para \\times + números'
  },
  {
    pattern: /(?<!\\)\bimes\b/g,
    replacement: '\\times',
    needsDelimiters: true,
    priority: 4,
    description: 'Corrige imes isolado para \\times'
  },
  {
    pattern: /\\rac\s*\{([^}]*)\}\s*\{([^}]*)\}/g,
    replacement: '\\frac{$1}{$2}',
    needsDelimiters: true,
    priority: 5,
    description: 'Corrige \\rac{}{} para \\frac{}{}'
  },
  {
    pattern: /\\extbf\s*\{([^}]*)\}/g,
    replacement: '**$1**',
    needsDelimiters: false,
    priority: 6,
    description: 'Converte \\extbf{} para **bold**'
  },
  {
    pattern: /\\imes\b/g,
    replacement: '\\times',
    needsDelimiters: true,
    priority: 7,
    description: 'Corrige \\imes para \\times'
  }
];

function applyMathDelimiters(text, command, commandPosition) {
  const beforeCommand = text.substring(0, commandPosition);
  const dollarsBeforeCount = (beforeCommand.match(/\$/g) || []).length;
  const isInMath = dollarsBeforeCount % 2 !== 0;
  
  if (isInMath) {
    return command;
  }
  
  return `$${command}$`;
}

function normalizeDelimiters(text) {
  let result = text;
  
  // Remover delimitadores vazios ou só com espaços
  result = result.replace(/\$\s*\$/g, '');
  
  // Consolidar múltiplos $ em um só
  result = result.replace(/\$+/g, '$');
  
  // Adicionar espaços ao redor dos delimitadores quando necessário
  result = result.replace(/(\S)\$(\S)/g, '$1 $ $2');
  result = result.replace(/(\S)\$([a-zA-Z])/g, '$1 $ $2');
  result = result.replace(/([a-zA-Z])\$(\S)/g, '$1 $ $2');
  
  return result;
}

function balanceDelimiters(text) {
  const dollars = text.match(/\$/g);
  if (!dollars) return text;
  
  if (dollars.length % 2 !== 0) {
    return text + '$';
  }
  
  return text;
}

function processLatexCorrections(str) {
  let result = str;
  
  // Aplicar correções de forma simples e direta
  latexCorrections
    .sort((a, b) => a.priority - b.priority)
    .forEach(correction => {
      result = result.replace(correction.pattern, (match, ...args) => {
        const replacement = match.replace(correction.pattern, correction.replacement);
        
        if (correction.needsDelimiters) {
          // Verificar contexto para ver se precisa de espaços
          const offset = args[args.length - 2];
          const beforeChar = result[offset - 1] || ' ';
          const afterChar = result[offset + match.length] || ' ';
          
          const needsSpaceBefore = /\S/.test(beforeChar);
          const needsSpaceAfter = /\S/.test(afterChar);
          
          let prefix = needsSpaceBefore ? ' ' : '';
          let suffix = needsSpaceAfter ? ' ' : '';
          
          return `${prefix}$${replacement}$${suffix}`;
        }
        
        return replacement;
      });
    });
  
  // Limpar espaços extras mas preservar espaços únicos
  result = result.replace(/\s{2,}/g, ' ').trim();
  
  // Normalizar delimitadores
  result = normalizeDelimiters(result);
  result = balanceDelimiters(result);
  
  return result;
}

// CASOS DE TESTE
const testCases = [
  {
    name: "Problema Principal: rac{8,00}{1,265}",
    original: "O resultado é rac{8,00}{1,265} = 6,32",
    expected: "O resultado é $\\frac{8,00}{1,265}$ = 6,32"
  },
  {
    name: "Problema Principal: imes26,5",
    original: "A multiplicação é imes26,5 metros",
    expected: "A multiplicação é $\\times 26,5$ metros"
  },
  {
    name: "Problema Principal: extbf{$ 1,68}",
    original: "O valor extbf{$ 1,68} está correto",
    expected: "O valor **$ 1,68** está correto"
  },
  {
    name: "Comando isolado: imes",
    original: "Símbolo de multiplicação: imes",
    expected: "Símbolo de multiplicação: $\\times$"
  },
  {
    name: "Múltiplos comandos",
    original: "Calcular rac{10}{5} imes 3 com extbf{resultado}",
    expected: "Calcular $\\frac{10}{5}$ $\\times$ 3 com **resultado**"
  },
  {
    name: "Comando com barra: \\rac",
    original: "Fração \\rac{1}{2} + \\imes 3",
    expected: "Fração $\\frac{1}{2}$ + $\\times$ 3"
  },
  {
    name: "Comando já correto",
    original: "Fração $\\frac{1}{2}$ já correta",
    expected: "Fração $\\frac{1}{2}$ já correta"
  }
];

function runTests() {
  console.log('🧪 VALIDAÇÃO DA ESTRATÉGIA ROBUSTA DE CORREÇÃO LATEX');
  console.log('=' .repeat(60));
  
  let totalTests = testCases.length;
  let passedTests = 0;
  
  testCases.forEach((testCase, index) => {
    const corrected = processLatexCorrections(testCase.original);
    const passed = corrected === testCase.expected;
    
    if (passed) passedTests++;
    
    console.log(`\n${index + 1}. ${testCase.name}`);
    console.log(`Status: ${passed ? '✅ PASSOU' : '❌ FALHOU'}`);
    console.log(`Original:  "${testCase.original}"`);
    console.log(`Esperado:  "${testCase.expected}"`);
    console.log(`Resultado: "${corrected}"`);
    
    if (!passed) {
      console.log(`⚠️  DIFERENÇA DETECTADA`);
    }
  });
  
  console.log('\n' + '=' .repeat(60));
  console.log('📊 RESUMO DOS TESTES');
  console.log(`Total de testes: ${totalTests}`);
  console.log(`Passou: ${passedTests}`);
  console.log(`Falhou: ${totalTests - passedTests}`);
  console.log(`Taxa de sucesso: ${Math.round((passedTests/totalTests)*100)}%`);
  
  if (passedTests === totalTests) {
    console.log('🎉 TODOS OS TESTES PASSARAM! Estratégia está funcionando corretamente.');
  } else {
    console.log('⚠️  Alguns testes falharam. Revise a estratégia.');
  }
}

// Executar testes
runTests();