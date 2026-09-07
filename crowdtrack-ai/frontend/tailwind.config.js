/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        panel: '#120b0d',
        panelAlt: '#1a0f13',
        accent: '#ff4d4d',
        accentSoft: '#ff7a7a',
        slateDeep: '#0f172a',
        success: '#34d399',
        warning: '#fbbf24',
        danger: '#f87171'
      },
      boxShadow: {
        glow: '0 0 0 1px rgba(255,82,82,0.24), 0 12px 30px rgba(239,68,68,0.18)'
      }
    }
  },
  plugins: []
};
