//const html = require("@html-eslint/eslint-plugin");
//const parser = require("@html-eslint/parser");

module.exports = [
  // recommended configuration included in the plugin
  //html.configs["flat/recommended"],
  // your own configurations.
  {
    files: ["**/*.html"],
    plugins: {
    },
    languageOptions: {
        //parser,
    },
    rules: {
    },
  },
];
