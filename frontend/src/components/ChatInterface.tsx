import React, { useState, useRef, useEffect } from 'react';
import { Mic, Send, Bot, User, Loader2, StopCircle, Bell } from 'lucide-react';
import { cn } from '../lib/utils';
import axios from 'axios';
import API_URL from '../config/api';
import { FlightCard } from './FlightCard';
import { HotelCard } from './HotelCard';
import { VoiceOrb } from './VoiceOrb';
import type { OrbState } from './VoiceOrb';
import { BookingModal } from './BookingModal';
import { HotelBookingModal } from './HotelBookingModal';
import { ProfileModal } from './ProfileModal';
import { TicketCard } from './TicketCard';
import { HotelTicketCard } from './HotelTicketCard';
import { MyTripsModal } from './MyTripsModal';
import { NotificationsModal } from './NotificationsModal';
import { ProfilesCRM } from './ProfilesCRM';

interface Message {
    role: 'user' | 'assistant' | 'tool' | 'system';
    content: string;
    tool_calls?: any[];
    tool_call_id?: string;
    metadata?: any;
}

export const ChatInterface: React.FC = () => {
    // ... (state) ...



    const [messages, setMessages] = useState<Message[]>([
        { role: 'assistant', content: "Hola! Soy Biatriz, tu asistente de viajes. ¿A dónde te gustaría ir?" }
    ]);
    const [input, setInput] = useState('');
    const [orbState, setOrbState] = useState<OrbState>('idle');
    const scrollRef = useRef<HTMLDivElement>(null);

    // Modal State
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [isHotelModalOpen, setIsHotelModalOpen] = useState(false);
    const [isProfileOpen, setIsProfileOpen] = useState(false);
    const [isTripsOpen, setIsTripsOpen] = useState(false);
    const [isNotificationsOpen, setIsNotificationsOpen] = useState(false);
    const [isCRMOpen, setIsCRMOpen] = useState(false);
    const [unreadCount] = useState(0);
    const [selectedFlight, setSelectedFlight] = useState<any>(null);
    const [selectedHotel, setSelectedHotel] = useState<any>(null);

    // Speech Recognition Refs
    const recognitionRef = useRef<any>(null);
    const isListeningRef = useRef(false);

    useEffect(() => {
        // console.log("DEBUG: Current Messages State:", messages);
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [messages]);

    // Initialize Speech Recognition
    useEffect(() => {
        if ('webkitSpeechRecognition' in window) {
            const SpeechRecognition = (window as any).webkitSpeechRecognition;
            recognitionRef.current = new SpeechRecognition();
            recognitionRef.current.continuous = false; // Stop after one sentence for turn-taking
            recognitionRef.current.interimResults = false;
            recognitionRef.current.lang = 'es-ES'; // Default to Spanish as per user language

            recognitionRef.current.onstart = () => {
                setOrbState('listening');
                isListeningRef.current = true;
            };

            recognitionRef.current.onend = () => {
                if (isListeningRef.current) {
                    // If it stopped naturally but we didn't explicitly stop it, maybe restart?
                    // For now, let's go to processing if we have input, or idle.
                    setOrbState('idle');
                    isListeningRef.current = false;
                }
            };

            recognitionRef.current.onresult = (event: any) => {
                const transcript = event.results[0][0].transcript;
                setInput(transcript);
                handleSendMessage(transcript); // Auto-send on voice end
            };
        }
    }, []);

    const toggleListening = () => {
        if (isListeningRef.current) {
            recognitionRef.current?.stop();
            isListeningRef.current = false;
            setOrbState('idle');
        } else {
            recognitionRef.current?.start();
            isListeningRef.current = true;
            setOrbState('listening');
        }
    };

    const speakResponse = (text: string) => {
        if ('speechSynthesis' in window) {
            // Cancel any ongoing speech
            window.speechSynthesis.cancel();

            const utterance = new SpeechSynthesisUtterance(text);
            utterance.lang = 'es-ES';

            // Try to find a female voice (Google, Microsoft, or generic)
            const voices = window.speechSynthesis.getVoices();
            const preferredVoice = voices.find(v =>
                (v.name.includes('Google') && v.name.includes('Español')) ||
                (v.name.includes('Paulina')) ||
                (v.name.includes('Monica')) ||
                (v.name.includes('Samantha')) ||
                (v.lang.includes('es') && v.name.includes('Female'))
            );

            if (preferredVoice) {
                utterance.voice = preferredVoice;
            }

            utterance.rate = 1.1; // Slightly faster/more natural
            utterance.pitch = 1.0;

            utterance.onstart = () => setOrbState('speaking');
            utterance.onend = () => setOrbState('idle');
            window.speechSynthesis.speak(utterance);
        }
    };

    const handleSendMessage = async (textOverride?: string) => {
        const textToSend = textOverride || input;
        if (!textToSend.trim()) return;

        const userMsg: Message = { role: 'user', content: textToSend };
        const newHistory = [...messages, userMsg];
        setMessages(newHistory);
        setInput('');
        setOrbState('processing');

        try {
            // Use axios with /v1/chat (like Vercel)
            const response = await axios.post(`${API_URL}/v1/chat`, {
                user_id: 'demo-user',
                messages: newHistory
            });

            const data = response.data;

            if (data.messages) {
                setMessages(data.messages);

                // Speak last assistant message
                const lastMsg = data.messages[data.messages.length - 1];
                if (lastMsg?.role === 'assistant' && lastMsg.content) {
                    speakResponse(lastMsg.content);
                }
            }

            setOrbState('idle');

        } catch (error) {
            console.error('Chat error:', error);
            setMessages(prev => [...prev, { role: 'assistant', content: 'Sorry, there was an error.' }]);
            setOrbState('idle');
        }
    };

    const handleBookClick = (flight: any) => {
        setSelectedFlight(flight);
        setIsModalOpen(true);
    };

    const confirmBooking = async (seatServiceId?: string, extraCost?: number, seatDesignator?: string) => {
        if (!selectedFlight) return;

        try {
            const finalAmount = parseFloat(selectedFlight.price) + (extraCost || 0);

            const response = await axios.post('http://localhost:8000/v1/book', null, {
                params: {
                    user_id: "demo-user",
                    offer_id: selectedFlight.offer_id,
                    provider: selectedFlight.provider,
                    amount: finalAmount,
                    seat_service_id: seatServiceId
                }
            });

            setIsModalOpen(false);

            // Show Ticket in Chat
            const pnr = response.data.pnr || "TEST-PNR";
            const ticketUrl = response.data.ticket_url; // Get ticket URL from backend
            setMessages(prev => [...prev, {
                role: 'system',
                content: 'Booking Confirmed',
                metadata: {
                    type: 'ticket',
                    pnr: pnr,
                    flight: selectedFlight,
                    passengerName: "Juan Pérez", // Updated to match profile
                    seatNumber: seatDesignator || "Any",
                    ticketUrl: ticketUrl  // NEW: Add ticket URL
                }
            }]);
            speakResponse("¡Reserva confirmada! Aquí tienes tu boleto.");

        } catch (e) {
            alert("Booking failed");
        }
    };

    const handleHotelBookClick = (hotel: any) => {
        // Transform hotel data to match HotelBookingModal expectations
        const transformedHotel = {
            ...hotel,
            // Flatten price structure
            price: hotel.price?.total || hotel.price || '0',
            currency: hotel.price?.currency || hotel.currency || 'USD',
            // Add address string if it's an object
            address: typeof hotel.address === 'object'
                ? `${hotel.address.cityName || ''}, ${hotel.address.countryCode || ''}`
                : hotel.address || 'Address not available',
            // Add default values for missing fields
            checkIn: hotel.checkIn || new Date().toISOString().split('T')[0],
            checkOut: hotel.checkOut || new Date(Date.now() + 5 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
            guests: hotel.guests || 2,
            rooms: hotel.rooms || 1,
            offer_id: hotel.hotelId || hotel.offer_id,
            provider: hotel.provider || 'liteapi',
        };

        console.log('Transformed hotel data:', transformedHotel);
        setSelectedHotel(transformedHotel);
        setIsHotelModalOpen(true);
    };

    const renderMessageContent = (msg: Message) => {
        // Handle Ticket
        if (msg.role === 'system' && msg.metadata?.type === 'ticket') {
            return (
                <div className="w-full flex justify-center py-4">
                    <TicketCard
                        pnr={msg.metadata.pnr}
                        flight={msg.metadata.flight}
                        passengerName={msg.metadata.passengerName}
                        seatNumber={msg.metadata.seatNumber}
                        ticketUrl={msg.metadata.ticketUrl}  // NEW: Pass ticket URL
                    />
                </div>
            );
        }

        if (msg.role === 'system' && msg.metadata?.type === 'hotel-ticket') {
            return (
                <div className="w-full flex justify-center py-4">
                    <HotelTicketCard
                        pnr={msg.metadata.pnr}
                        hotel={msg.metadata.hotel}
                        guestName={msg.metadata.guestName}
                    />
                </div>
            );
        }

        if (msg.role === 'tool') {
            try {
                const data = JSON.parse(msg.content);

                if (Array.isArray(data) && data.length > 0 && data[0].offer_id) {
                    return (
                        <div className="flex flex-col gap-2 mt-2 w-full">
                            <p className="text-xs text-gray-400 mb-1">Found {data.length} flights:</p>
                            <div className="flex overflow-x-auto gap-3 pb-2 snap-x no-scrollbar min-h-[200px]">
                                {data.map((flight: any) => (
                                    <div key={flight.offer_id} className="snap-center shrink-0">
                                        <FlightCard flight={flight} onBook={() => handleBookClick(flight)} />
                                    </div>
                                ))}
                            </div>
                        </div>
                    );
                } else if (Array.isArray(data) && data.length === 0) {
                    return <span className="text-gray-400 italic text-sm">No flights found for your search.</span>;
                }

                if (Array.isArray(data) && data.length > 0 && data[0].hotelId) {
                    return (
                        <div className="flex flex-col gap-2 mt-2 w-full">
                            <p className="text-xs text-gray-400 mb-1">Found {data.length} hotels:</p>
                            <div className="flex overflow-x-auto gap-3 pb-2 snap-x no-scrollbar">
                                {data.map((hotel: any) => (
                                    <div key={hotel.hotelId} className="snap-center shrink-0">
                                        <HotelCard hotel={hotel} onBook={() => handleHotelBookClick(hotel)} />
                                    </div>
                                ))}
                            </div>
                        </div>
                    );
                }
                return (
                    <div className="w-full text-xs text-gray-500 bg-black/20 p-2 rounded mt-2">
                        <p className="font-bold text-red-400">DEBUG: Raw Tool Output</p>
                        <pre className="whitespace-pre-wrap mt-2 overflow-x-auto">
                            {JSON.stringify(data, null, 2)}
                        </pre>
                    </div>
                );
            } catch (e) {
                console.error("Error parsing tool content:", e);
                return <span className="text-red-400 text-xs">Error displaying results.</span>;
            }
        }
        return <span>{msg.content}</span>;
    };

    return (
        <div className="glass-panel h-screen flex flex-col relative overflow-hidden rounded-none border-0">
            {/* Background Gradient */}
            <div className="absolute inset-0 bg-gradient-to-b from-background via-background/90 to-primary/5 pointer-events-none" />

            {/* Header Controls */}
            <div className="absolute top-4 right-4 z-50 flex gap-2">
                <button
                    onClick={() => setIsNotificationsOpen(true)}
                    className="relative w-10 h-10 rounded-full bg-card/50 backdrop-blur-md border border-white/10 flex items-center justify-center text-gray-300 hover:text-white hover:bg-white/10 transition-all shadow-lg"
                    title="Notifications"
                >
                    <Bell size={20} />
                    {unreadCount > 0 && (
                        <span className="absolute -top-1 -right-1 bg-red-500 text-white text-xs font-bold rounded-full w-5 h-5 flex items-center justify-center animate-pulse">
                            {unreadCount}
                        </span>
                    )}
                </button>
                <button
                    onClick={() => setIsTripsOpen(true)}
                    className="px-4 h-10 rounded-full bg-card/50 backdrop-blur-md border border-white/10 flex items-center justify-center text-gray-300 hover:text-white hover:bg-white/10 transition-all shadow-lg text-sm font-medium"
                >
                    My Trips
                </button>
                <button
                    onClick={() => setIsCRMOpen(true)}
                    className="px-4 h-10 rounded-full bg-primary/20 backdrop-blur-md border border-primary/30 flex items-center justify-center text-primary hover:text-white hover:bg-primary transition-all shadow-lg text-sm font-medium"
                >
                    CRM
                </button>
                <button
                    onClick={() => setIsProfileOpen(true)}
                    className="w-10 h-10 rounded-full bg-card/50 backdrop-blur-md border border-white/10 flex items-center justify-center text-gray-300 hover:text-white hover:bg-white/10 transition-all shadow-lg"
                    title="Edit Profile"
                >
                    <User size={20} />
                </button>
            </div>

            {/* ORB CONTAINER (Centered & Interactive) */}
            <div className="flex-1 flex flex-col items-center justify-center relative z-10 min-h-[300px]">
                <button
                    onClick={toggleListening}
                    className="relative focus:outline-none group cursor-pointer"
                >
                    <VoiceOrb state={orbState} />

                    {/* Tap Hint */}
                    {orbState === 'idle' && (
                        <span className="absolute -bottom-16 left-1/2 -translate-x-1/2 text-sm text-gray-400 opacity-50 group-hover:opacity-100 transition-opacity whitespace-nowrap">
                            Tap to Speak
                        </span>
                    )}
                </button>
            </div>

            {/* CHAT HISTORY (Overlay/Bottom) */}
            <div className="flex-1 overflow-y-auto space-y-4 px-4 relative z-10 mask-image-gradient" ref={scrollRef}>
                {messages.map((msg, i) => {
                    // NUCLEAR DEBUG: SHOW EVERYTHING
                    // if (msg.role === 'assistant' && msg.tool_calls) return null;

                    return (
                        <div key={i} className={cn(
                            "flex gap-3 max-w-[90%] animate-in fade-in slide-in-from-bottom-4 duration-500",
                            msg.role === 'user' ? "ml-auto flex-row-reverse" : "mr-auto",
                            msg.role === 'tool' ? "w-full max-w-full" : ""
                        )}>
                            {msg.role !== 'tool' && (
                                <div className={cn(
                                    "w-8 h-8 rounded-full flex items-center justify-center shrink-0 shadow-lg",
                                    msg.role === 'user' ? "bg-primary text-primary-foreground" : "bg-card border border-white/10"
                                )}>
                                    {msg.role === 'user' ? <User size={16} /> : <Bot size={16} />}
                                </div>
                            )}

                            <div className={cn(
                                "rounded-2xl text-sm overflow-hidden shadow-sm backdrop-blur-sm",
                                msg.role === 'user'
                                    ? "bg-primary/20 text-foreground p-3 rounded-tr-none border border-primary/20"
                                    : msg.role === 'tool'
                                        ? "bg-transparent w-full"
                                        : "bg-card/50 text-foreground p-3 rounded-tl-none border border-white/5"
                            )}>
                                {/* DEBUG BADGE REMOVED */}
                                {renderMessageContent(msg)}
                            </div>
                        </div>
                    );
                })}
            </div>

            {/* INPUT AREA (Bottom Fixed) */}
            <div className="p-4 relative z-20 bg-background/80 backdrop-blur-lg border-t border-white/5">
                <div className="flex gap-2 items-center max-w-2xl mx-auto">
                    <button
                        onClick={toggleListening}
                        className={cn(
                            "p-3 rounded-full transition-all duration-300 shadow-lg hover:scale-105 active:scale-95",
                            orbState === 'listening'
                                ? "bg-red-500 text-white animate-pulse shadow-red-500/50"
                                : "bg-card border border-white/10 text-white hover:bg-white/10"
                        )}
                    >
                        {orbState === 'listening' ? <StopCircle size={24} /> : <Mic size={24} />}
                    </button>

                    <input
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
                        placeholder="Type or speak..."
                        className="glass-input flex-1 h-12 rounded-full px-6"
                    />

                    <button
                        onClick={() => handleSendMessage()}
                        disabled={orbState === 'processing'}
                        className="p-3 rounded-full bg-primary text-white shadow-lg shadow-primary/30 hover:bg-primary/90 transition-all hover:scale-105 active:scale-95 disabled:opacity-50"
                    >
                        {orbState === 'processing' ? <Loader2 size={24} className="animate-spin" /> : <Send size={24} />}
                    </button>
                </div>
            </div>

            {/* BOOKING MODAL */}
            <BookingModal
                isOpen={isModalOpen}
                onClose={() => setIsModalOpen(false)}
                onConfirm={confirmBooking}
                flight={selectedFlight}
                preferences={{
                    seat: "Window (AI Selected)", // Hardcoded for demo until we fetch profile in frontend
                    baggage: "1 Checked Bag (AI Selected)"
                }}
            />

            {/* HOTEL BOOKING MODAL */}
            <HotelBookingModal
                isOpen={isHotelModalOpen}
                onClose={() => setIsHotelModalOpen(false)}
                hotel={selectedHotel}
            />

            {/* PROFILE MODAL */}
            <ProfileModal
                isOpen={isProfileOpen}
                onClose={() => setIsProfileOpen(false)}
            />

            {/* MY TRIPS MODAL */}
            <MyTripsModal
                isOpen={isTripsOpen}
                onClose={() => setIsTripsOpen(false)}
            />

            {/* NOTIFICATIONS MODAL */}
            <NotificationsModal
                isOpen={isNotificationsOpen}
                onClose={() => setIsNotificationsOpen(false)}
                userId="demo-user"
            />

            {/* PROFILES CRM MODAL */}
            <ProfilesCRM
                isOpen={isCRMOpen}
                onClose={() => setIsCRMOpen(false)}
            />
        </div>
    );
};

