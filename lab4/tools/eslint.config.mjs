// eslint.config.js (or tools/eslint.config.js and pass -c)
import globals from "globals";

export default [
  {
    files: ["server/static/**/*.js"],
    languageOptions: {
      sourceType: "module",
      ecmaVersion: 2022,
      globals: {
        ...globals.browser,
        Tabulator: "readonly",
        show_messages: "readonly",
      },
    },
    rules: {
      "no-console": "off",
    },
  },
];
