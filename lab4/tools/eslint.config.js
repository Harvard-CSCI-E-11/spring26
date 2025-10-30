module.exports = [
  {
    files: ["server/static/**/*.js"],
    languageOptions: { sourceType: "module" },
    rules: {
      "no-unused-vars": "warn",
      "no-undef": "error",
      "semi": ["error", "always"],
      "quotes": ["error", "double"]
    },
  },
];
