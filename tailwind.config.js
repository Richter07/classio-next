/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./app/**/*.{js,jsx,ts,tsx}', './components/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: { brand: '#075e54', 'brand-soft': '#e7f6f2', sun: '#f6c445' }
    }
  },
  plugins: []
};
