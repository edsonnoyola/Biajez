import { ChatInterface } from './components/ChatInterface';
import { Rocket } from 'lucide-react';
import { loadStripe } from '@stripe/stripe-js';
import { Elements } from '@stripe/react-stripe-js';

// Initialize Stripe with publishable key from environment variable
const stripePromise = loadStripe(
    import.meta.env.VITE_STRIPE_PUBLISHABLE_KEY ||
    'pk_test_51SLzdO0ikaK8tETEV1QaPWaoXQeps3u4L8jW8q2mElOEBGr35hBrHbWNRfzyMy7sYLR2AlmjAOoC4It272gJZM8100ppJLap4v'
);

function App() {
    return (
        <Elements stripe={stripePromise}>
            <div className="min-h-screen bg-background text-foreground font-sans selection:bg-primary/30 flex flex-col">
                {/* Minimal Header */}
                <header className="absolute top-0 left-0 w-full p-6 flex items-center justify-between z-50 pointer-events-none">
                    <div className="flex items-center gap-3 pointer-events-auto">
                        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary to-accent flex items-center justify-center shadow-lg shadow-primary/20">
                            <Rocket className="text-white" size={24} />
                        </div>
                        <h1 className="text-2xl font-bold tracking-tight">Biatriz</h1>
                    </div>
                </header>

                {/* Main Full Screen Chat */}
                <main className="flex-1 relative">
                    <ChatInterface />
                </main>
            </div>
        </Elements>
    );
}

export default App;
