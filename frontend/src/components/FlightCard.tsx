import React from 'react';
import { Plane, Check, Clock, Wifi, Coffee, Calendar } from 'lucide-react';

interface FlightSegment {
    carrier_code: string;
    flight_number: string;
    departure_iata: string;
    arrival_iata: string;
    departure_time: string;
    arrival_time: string;
    duration: string;
}

interface FlightOffer {
    offer_id: string;
    provider: string;
    price: number;
    currency: string;
    segments: FlightSegment[];
    duration_total: string;
    cabin_class: string;
    refundable: boolean;
}

interface FlightCardProps {
    flight: FlightOffer;
    onBook: (offerId: string, provider: string, amount: number) => void;
}

export const FlightCard: React.FC<FlightCardProps> = ({ flight, onBook }) => {
    if (!flight.segments || flight.segments.length === 0) return null;
    const firstSegment = flight.segments[0];
    const lastSegment = flight.segments[flight.segments.length - 1];
    const isMultiLeg = flight.segments.length > 1;
    const stopCount = flight.segments.length - 1;

    const formatTime = (isoString: string) => {
        const date = new Date(isoString);
        const time = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
        const dateStr = date.toLocaleDateString([], { month: 'short', day: 'numeric' });
        return { time, date: dateStr };
    };

    const depTime = formatTime(firstSegment.departure_time);
    const arrTime = formatTime(lastSegment.arrival_time);

    // Calculate if it's a good deal (mock logic - could be enhanced)
    const isGoodDeal = flight.price < 500;

    return (
        <div className="group relative bg-gradient-to-br from-gray-900/95 to-gray-800/95 backdrop-blur-xl border border-white/10 rounded-2xl p-5 mb-4 hover:border-primary/50 hover:shadow-2xl hover:shadow-primary/10 transition-all duration-300 cursor-pointer max-w-2xl w-full overflow-hidden">
            {/* Background Gradient Effect */}
            <div className="absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-accent/5 opacity-0 group-hover:opacity-100 transition-opacity duration-500" />

            {/* Good Deal Badge */}
            {isGoodDeal && (
                <div className="absolute -right-8 top-4 bg-gradient-to-r from-green-500 to-emerald-600 text-white text-xs font-bold px-8 py-1 rotate-45 shadow-lg">
                    Best Deal
                </div>
            )}

            <div className="relative z-10">
                {/* Header - Airline Info & Price */}
                <div className="flex justify-between items-start mb-5">
                    <div className="flex items-center gap-3">
                        <div className="w-12 h-12 rounded-xl bg-white shadow-lg flex items-center justify-center overflow-hidden ring-2 ring-white/10">
                            <img
                                src={`https://pics.avs.io/200/200/${firstSegment.carrier_code}.png`}
                                alt={firstSegment.carrier_code}
                                className="w-full h-full object-contain p-1"
                                onError={(e) => {
                                    const target = e.target as HTMLImageElement;
                                    target.style.display = 'none';
                                    if (!target.parentElement?.querySelector('.fallback-icon')) {
                                        const icon = document.createElement('div');
                                        icon.className = 'fallback-icon text-gray-600';
                                        icon.innerHTML = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 12h20"/><path d="M13 2l9 10-9 10"/></svg>';
                                        target.parentElement?.appendChild(icon);
                                    }
                                }}
                            />
                        </div>
                        <div>
                            <p className="font-bold text-base text-white">{firstSegment.carrier_code} {firstSegment.flight_number}</p>
                            <p className="text-xs text-gray-400 capitalize flex items-center gap-1">
                                {flight.cabin_class.replace('_', ' ')}
                            </p>
                        </div>
                    </div>
                    <div className="text-right">
                        <div className="flex items-baseline gap-1">
                            <span className="text-xs text-gray-400">$</span>
                            <p className="text-3xl font-bold bg-gradient-to-r from-accent via-primary to-accent bg-clip-text text-transparent">
                                {flight.price}
                            </p>
                        </div>
                        <p className="text-xs text-gray-500 mt-1">{flight.currency} por persona</p>
                    </div>
                </div>

                {/* Flight Route Timeline */}
                <div className="relative mb-5">
                    <div className="flex items-center justify-between">
                        {/* Departure */}
                        <div className="flex flex-col items-start flex-1">
                            <p className="text-3xl font-bold text-white">{firstSegment.departure_iata}</p>
                            <p className="text-lg font-semibold text-gray-300 mt-1">{depTime.time}</p>
                            <p className="text-xs text-gray-500 flex items-center gap-1 mt-1">
                                <Calendar size={10} />
                                {depTime.date}
                            </p>
                        </div>

                        {/* Timeline */}
                        <div className="flex-[2] px-6 flex flex-col items-center">
                            {/* Duration */}
                            <div className="flex items-center gap-2 mb-2">
                                <Clock size={14} className="text-gray-400" />
                                <p className="text-sm font-medium text-gray-300">{flight.duration_total}</p>
                            </div>

                            {/* Visual Timeline */}
                            <div className="w-full relative">
                                <div className="h-[2px] w-full bg-gradient-to-r from-primary/30 via-accent to-primary/30" />

                                {/* Departure Dot */}
                                <div className="absolute left-0 top-1/2 -translate-y-1/2 w-3 h-3 bg-primary rounded-full ring-4 ring-primary/20" />

                                {/* Stops */}
                                {isMultiLeg && (
                                    <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
                                        <div className="w-2 h-2 bg-amber-400 rounded-full ring-4 ring-amber-400/20" />
                                    </div>
                                )}

                                {/* Plane Icon */}
                                <div className="absolute left-1/2 -translate-x-1/2 -top-5">
                                    <Plane size={16} className="text-accent transform rotate-90" />
                                </div>

                                {/* Arrival Dot */}
                                <div className="absolute right-0 top-1/2 -translate-y-1/2 w-3 h-3 bg-accent rounded-full ring-4 ring-accent/20" />
                            </div>

                            {/* Stops Info */}
                            <p className="text-xs text-gray-400 mt-2">
                                {isMultiLeg ? (
                                    <span className="text-amber-400 font-medium">{stopCount} escala{stopCount > 1 ? 's' : ''}</span>
                                ) : (
                                    <span className="text-green-400 font-medium flex items-center gap-1">
                                        <Check size={12} /> Vuelo directo
                                    </span>
                                )}
                            </p>
                        </div>

                        {/* Arrival */}
                        <div className="flex flex-col items-end flex-1">
                            <p className="text-3xl font-bold text-white">{lastSegment.arrival_iata}</p>
                            <p className="text-lg font-semibold text-gray-300 mt-1">{arrTime.time}</p>
                            <p className="text-xs text-gray-500 flex items-center gap-1 mt-1">
                                <Calendar size={10} />
                                {arrTime.date}
                            </p>
                        </div>
                    </div>
                </div>

                {/* Features & CTA */}
                <div className="flex items-center justify-between pt-4 border-t border-white/10">
                    <div className="flex gap-2 flex-wrap">
                        {/* Refundable Badge */}
                        {flight.refundable && (
                            <span className="flex items-center gap-1.5 text-xs bg-green-500/20 text-green-400 px-3 py-1.5 rounded-lg border border-green-500/30 font-medium">
                                <Check size={12} /> Reembolsable
                            </span>
                        )}

                        {/* Mock Amenities - Can be enhanced with real data */}
                        <span className="flex items-center gap-1.5 text-xs bg-blue-500/20 text-blue-400 px-3 py-1.5 rounded-lg border border-blue-500/30">
                            <Wifi size={12} /> WiFi
                        </span>

                        {flight.cabin_class !== 'ECONOMY' && (
                            <span className="flex items-center gap-1.5 text-xs bg-purple-500/20 text-purple-400 px-3 py-1.5 rounded-lg border border-purple-500/30">
                                <Coffee size={12} /> Comidas
                            </span>
                        )}
                    </div>

                    <button
                        onClick={() => onBook(flight.offer_id, flight.provider, flight.price)}
                        className="bg-gradient-to-r from-primary to-accent hover:from-primary/90 hover:to-accent/90 text-white text-sm font-bold px-6 py-2.5 rounded-xl transition-all duration-200 shadow-lg shadow-primary/25 hover:shadow-primary/40 hover:scale-105 active:scale-95"
                    >
                        Reservar →
                    </button>
                </div>

                {/* Provider Badge */}
                <div className="absolute bottom-3 left-3">
                    <span className="text-[9px] uppercase tracking-wider text-gray-600 bg-white/5 px-2 py-1 rounded border border-white/5">
                        Vía {flight.provider === 'SIMULATION' ? 'TEST' : flight.provider}
                    </span>
                </div>
            </div>
        </div>
    );
};
