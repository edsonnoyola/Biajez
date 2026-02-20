import React from 'react';
import { Plane } from 'lucide-react';
import API_URL from '../config/api';

interface TicketCardProps {
    pnr: string;
    passengerName: string;
    flight: any;
    seatNumber?: string;
    ticketUrl?: string;  // NEW: URL to generated HTML ticket
}

export const TicketCard: React.FC<TicketCardProps> = ({ pnr, passengerName, flight, seatNumber, ticketUrl }) => {
    const segment = flight.segments[0];

    return (
        <div className="w-full max-w-sm mx-auto bg-white text-black rounded-3xl overflow-hidden shadow-2xl relative animate-in zoom-in-95 duration-500">
            {/* Top Section: Flight Info */}
            <div className="p-6 bg-gradient-to-br from-blue-600 to-blue-800 text-white relative overflow-hidden">
                <div className="absolute top-0 right-0 p-4 opacity-10">
                    <Plane size={120} />
                </div>

                <div className="flex justify-between items-start relative z-10">
                    <div>
                        <p className="text-blue-200 text-xs font-bold uppercase tracking-wider">Boarding Pass</p>
                        <h2 className="text-3xl font-bold mt-1">{segment.departure_iata}</h2>
                        <p className="text-blue-100 text-sm">{(segment.departure_time || segment.departure_at || "").split(/T| /)[1]?.substring(0, 5)}</p>
                    </div>
                    <div className="flex flex-col items-center justify-center pt-2">
                        <Plane size={24} className="rotate-90 text-blue-300" />
                        <p className="text-xs text-blue-300 mt-1">{flight.duration_total}</p>
                    </div>
                    <div className="text-right">
                        <p className="text-blue-200 text-xs font-bold uppercase tracking-wider">To</p>
                        <h2 className="text-3xl font-bold mt-1">{segment.arrival_iata}</h2>
                        <p className="text-blue-100 text-sm">{(segment.arrival_time || segment.arrival_at || "").split(/T| /)[1]?.substring(0, 5)}</p>
                    </div>
                </div>
            </div>

            {/* Middle Section: Passenger Details */}
            <div className="p-6 space-y-4 relative">
                {/* Perforated Line Effect */}
                <div className="absolute top-0 left-0 w-full h-4 -mt-2 flex justify-between items-center px-1">
                    {[...Array(15)].map((_, i) => (
                        <div key={i} className="w-2 h-2 rounded-full bg-gray-900" />
                    ))}
                </div>

                <div className="grid grid-cols-2 gap-4 pt-2">
                    <div>
                        <p className="text-gray-400 text-xs uppercase font-bold">Passenger</p>
                        <p className="font-bold truncate">{passengerName}</p>
                    </div>
                    <div>
                        <p className="text-gray-400 text-xs uppercase font-bold">Date</p>
                        <p className="font-bold">{(segment.departure_time || segment.departure_at || "").split(/T| /)[0]}</p>
                    </div>
                    <div>
                        <p className="text-gray-400 text-xs uppercase font-bold">Flight</p>
                        <p className="font-bold">{segment.carrier_code} {segment.number}</p>
                    </div>
                    <div>
                        <p className="text-gray-400 text-xs uppercase font-bold">Seat</p>
                        <p className="font-bold text-blue-600">{seatNumber || "Any"}</p>
                    </div>
                </div>
            </div>

            {/* Bottom Section: Barcode */}
            <div className="p-6 pt-0 flex flex-col items-center justify-center space-y-2">
                <div className="w-full h-16 bg-gray-100 rounded-lg flex items-center justify-center border border-dashed border-gray-300">
                    {/* Mock Barcode */}
                    <div className="flex gap-1 h-10 items-center opacity-50">
                        {[...Array(20)].map((_, i) => (
                            <div key={i} className={`w-${Math.random() > 0.5 ? '1' : '2'} h-full bg-black`} />
                        ))}
                    </div>
                </div>
                <p className="text-xs text-gray-400 font-mono tracking-widest">PNR: {pnr}</p>

                {/* Download Ticket Button */}
                {ticketUrl && (
                    <a
                        href={`${API_URL}${ticketUrl}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="mt-4 w-full py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-bold text-sm transition-colors flex items-center justify-center gap-2"
                    >
                        📥 Ver Boleto Completo
                    </a>
                )}
            </div>
        </div>
    );
};
