/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: {
          start: '#8B5A3C',
          end: '#D4753E',
        },
        accent: '#CC5500',
        background: '#F5F1E8',
        surface: '#EAE3D2',
        success: '#6B8E23',
        warning: '#D4753E',
        error: '#A52A2A',
        text: {
          primary: '#2D1B0E',
          secondary: '#4A3728',
          muted: '#7B6C5D',
        },
      },
      fontFamily: {
        sans: [
          '-apple-system',
          'BlinkMacSystemFont',
          'Segoe UI',
          'Roboto',
          'Oxygen',
          'Ubuntu',
          'Cantarell',
          'sans-serif',
        ],
      },
    },
  },
  plugins: [],
};
