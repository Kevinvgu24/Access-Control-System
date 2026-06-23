/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        green:   '#00e676',
        red:     '#ff5252',
        amber:   '#ffab00',
        blue:    '#40c4ff',
        surface: '#111514',
        raised:  '#0e1211',
        dark:    '#0c0e0f',
        darker:  '#0a0c0d',
        line:    '#1c2420',
      },
      fontFamily: {
        sans: ['Syne', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'monospace'],
      },
    },
  },
  plugins: [],
}
