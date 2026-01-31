/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            colors: {
                background: "#09090b", // Zinc 950
                foreground: "#fafafa", // Zinc 50
                primary: {
                    DEFAULT: "#3b82f6", // Blue 500
                    foreground: "#ffffff",
                },
                secondary: {
                    DEFAULT: "#27272a", // Zinc 800
                    foreground: "#fafafa",
                },
                accent: {
                    DEFAULT: "#8b5cf6", // Violet 500
                    foreground: "#ffffff",
                },
                card: {
                    DEFAULT: "rgba(24, 24, 27, 0.6)", // Zinc 900 with opacity
                    foreground: "#fafafa",
                },
                border: "rgba(255, 255, 255, 0.1)",
            },
            fontFamily: {
                sans: ['Inter', 'sans-serif'],
            },
            animation: {
                "pulse-slow": "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
            },
        },
    },
    plugins: [],
}
