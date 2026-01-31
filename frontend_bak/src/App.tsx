import React, { useState } from 'react';
import { ChatInterface } from './components/ChatInterface';
import { FlightSearch } from './components/FlightSearch';
import { FlightResults } from './components/FlightResults';
import { Rocket } from 'lucide-react';
import axios from 'axios';

function App() {
    const [flights, setFlights] = useState<any[]>([]);
    const [activeTab, setActiveTab] = useState<'chat' | 'search'>('chat');

    const handleBook = async (offerId: string, provider: string, amount: number) => {
        try {
            const response = await axios.post('http://localhost:8000/v1/book', null, {
                params: {
                    user_id: "demo-user", // Hardcoded
                    offer_id: offerId,
                    provider: provider,
                    amount: amount
                }
            });
            alert(`Booking Successful! PNR: ${response.data.pnr}`);
        } catch (error) {
            alert('Booking Failed. Check console.');
            console.error(error);
        }
    };

    return (
        <div className="min-h-screen bg-background text-foreground p-4 md:p-8 font-sans selection:bg-primary/30">
            <div className="max-w-6xl mx-auto space-y-8">

                {/* Header */}
                <header className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary to-accent flex items-center justify-center shadow-lg shadow-primary/20">
                            <Rocket className="text-white" size={24} />
                        </div>
                        <h1 className="text-2xl font-bold tracking-tight">Antigravity</h1>
                    </div>

                    <div className="flex gap-2 bg-secondary/50 p-1 rounded-lg">
                        <button
                            onClick={() => setActiveTab('chat')}
                            className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all ${activeTab === 'chat' ? 'bg-card shadow-sm text-primary' : 'text-gray-400 hover:text-foreground'}`}
                        >
                            AI Assistant
                        </button>
                        <button
                            onClick={() => setActiveTab('search')}
                            className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all ${activeTab === 'search' ? 'bg-card shadow-sm text-primary' : 'text-gray-400 hover:text-foreground'}`}
                        >
                            Manual Search
                        </button>
                    </div>
                </header>

                {/* Main Content */}
                <main className="grid grid-cols-1 lg:grid-cols-3 gap-8">

                    {/* Left Column: Chat (Always visible on desktop, or toggled) */}
                    <div className={`lg:col-span-1 ${activeTab === 'chat' ? 'block' : 'hidden lg:block'}`}>
                        <ChatInterface />
                    </div>

                    {/* Right Column: Content */}
                    <div className={`lg:col-span-2 ${activeTab === 'search' ? 'block' : 'hidden lg:block'}`}>
                        <div className="space-y-8">
                            <div className="glass-panel p-8 text-center space-y-4 bg-gradient-to-b from-primary/5 to-transparent border-primary/10">
                                <h2 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-gray-400">
                                    Where to next?
                                </h2>
                                <p className="text-gray-400 max-w-md mx-auto">
                                    Experience the future of corporate travel. Book flights and hotels with the power of AI.
                                </p>
                            </div>

                            <FlightSearch onSearch={setFlights} />
                            <FlightResults flights={flights} onBook={handleBook} />
                        </div>
                    </div>

                </main>
            </div>
        </div>
    );
}

export default App;
