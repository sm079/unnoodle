/** @type {import('prettier').Config} */
export default {
  singleQuote: true,
  printWidth: 140,
  trailingComma: 'none',
  arrowParens: 'avoid',
  plugins: ['prettier-plugin-tailwindcss'],
  tailwindStylesheet: './apps/web/src/app/globals.css',
  tailwindFunctions: ['cn', 'cva']
};
