import React from 'react';
import { Clock, DollarSign, ArrowRight } from 'lucide-react';

interface Flight {
    offer_id: string;
    provider: string;
    price: number;
    currency: string;
    duration_total: string;
    segments: any[];
}

interface FlightResultsProps {
    flights: Flight[];
    onBook: (offerId: string, provider: string, amount: number) => void;
}

export const FlightResults: React.FC<FlightResultsProps> = ({ flights, onBook }) => {
    if (flights.length === 0) return null;

    return (
        <div className="space-y-4">
            <h3 className="text-lg font-medium opacity-80">Available Flights</h3>
            <div className="grid gap-4">
                {flights.map((flight) => (
                    <div key={flight.offer_id} className="glass-panel p-4 flex flex-col md:flex-row items-center justify-between gap-4 hover:border-primary/50 transition-colors">

                        {/* Flight Info */}
                        <div className="flex-1 space-y-2">
                            <div className="flex items-center gap-2 text-sm text-gray-400">
                                <span className="px-2 py-0.5 rounded bg-secondary text-xs font-mono">{flight.provider}</span>
                                <span>{flight.duration_total.replace("PT", "").toLowerCase()}</span>
                            </div>

                            <div className="flex items-center gap-4 text-lg font-semibold">
                                <span>{flight.segments[0].departure_iata}</span>
                                <ArrowRight size={16} className="text-gray-500" />
                                <span>{flight.segments[flight.segments.length - 1].arrival_iata}</span>
                            </div>

                            <div className="text-sm text-gray-400">
                                {flight.segments[0].carrier_code} {flight.segments[0].flight_number}
                            </div>
                        </div>

                        {/* Price & Action */}
                        <div className="flex flex-col items-end gap-2">
                            <div className="text-2xl font-bold text-primary flex items-center">
                                <DollarSign size={20} />
                                {flight.price}
                            </div>
                            <button
                                onClick={() => onBook(flight.offer_id, flight.provider, flight.price)}
                                className="glass-button text-sm px-6"
                            >
                                Book Now
                            </button>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};
