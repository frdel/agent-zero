#!/usr/bin/env node

const vm = require('vm');
const path = require('path');

// Create a comprehensive context with all important global objects
const context = vm.createContext({
  ...global,
  require: require,
  __filename: path.join(process.cwd(), 'eval.js'),
  __dirname: process.cwd(),
  module: { exports: {} },
  exports: module.exports,
  console: console,
  process: process,
  Buffer: Buffer,
  setTimeout: setTimeout,
  setInterval: setInterval,
  setImmediate: setImmediate,
  clearTimeout: clearTimeout,
  clearInterval: clearInterval,
  clearImmediate: clearImmediate
});

const code = process.argv[2];
const wrappedCode = `
  (async function() {
    try {
      const __result__ = await eval(${JSON.stringify(code)});
      if (__result__ !== undefined) console.log('Out[1]:', __result__);
    } catch (error) {
      console.error(error);
    }
  })();
`;

vm.runInContext(wrappedCode, context, {
  filename: 'eval.js',
  lineOffset: -2,
  columnOffset: 0,
}).catch(console.error);