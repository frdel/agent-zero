#!/usr/bin/env node

const vm = require('vm');
const path = require('path');
const Module = require('module');

 // Enhance `require` to search CWD and parent directories first, then globally
function customRequire(moduleName) {
  let currentDir = process.cwd();
  const root = path.parse(currentDir).root;

  do {
    try {
      const modulePath = path.join(currentDir, 'node_modules', moduleName);
      return require(modulePath);
    } catch (err) {
      currentDir = path.dirname(currentDir);
    }
  } while (currentDir !== root);

  try {
    return require(moduleName);
  } catch (globalErr) {
    console.error(`Cannot find module: ${moduleName}`);
    throw globalErr;
  }
}

// Create the VM context
const context = vm.createContext({
  ...global,
  require: customRequire, // Use the custom require
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
  clearImmediate: clearImmediate,
});

// Retrieve the code from the command-line argument
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
