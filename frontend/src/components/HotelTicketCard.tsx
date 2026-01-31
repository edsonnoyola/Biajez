import React from 'react';
import { Bed, MapPin, Calendar } from 'lucide-react';

interface HotelTicketCardProps {
    pnr: string;
    guestName: string;
    hotel: any;
}

export const HotelTicketCard: React.FC<HotelTicketCardProps> = ({ pnr, guestName, hotel }) => {
    return (
        <div className="w-full max-w-sm mx-auto bg-white text-black rounded-3xl overflow-hidden shadow-2xl relative animate-in zoom-in-95 duration-500">
            {/* Top Section: Hotel Info */}
            <div className="p-6 bg-gradient-to-br from-purple-600 to-purple-800 text-white relative overflow-hidden">
                <div className="absolute top-0 right-0 p-4 opacity-10">
                    <Bed size={120} />
                </div>

                <div className="relative z-10">
                    <p className="text-purple-200 text-xs font-bold uppercase tracking-wider">Hotel Reservation</p>
                    <h2 className="text-2xl font-bold mt-2 leading-tight">{hotel.name}</h2>
                    <div className="flex items-center gap-1 mt-1 text-purple-100 text-sm">
                        <MapPin size={14} />
                        <p>{hotel.address?.cityName || "City Center"}</p>
                    </div>
                </div>
            </div>

            {/* Middle Section: Details */}
            <div className="p-6 space-y-4 relative">
                <div className="grid grid-cols-2 gap-4">
                    <div>
                        <p className="text-gray-400 text-xs uppercase font-bold">Guest</p>
                        <p className="font-bold truncate">{guestName}</p>
                    </div>
                    <div>
                        <p className="text-gray-400 text-xs uppercase font-bold">Confirmation</p>
                        <p className="font-bold text-purple-600">{pnr}</p>
                    </div>
                    <div>
                        <p className="text-gray-400 text-xs uppercase font-bold">Check-In</p>
                        <div className="flex items-center gap-1">
                            <Calendar size={14} className="text-gray-400" />
                            <p className="font-bold">15 Dec</p> {/* Mock Date */}
                        </div>
                    </div>
                    <div>
                        <p className="text-gray-400 text-xs uppercase font-bold">Check-Out</p>
                        <div className="flex items-center gap-1">
                            <Calendar size={14} className="text-gray-400" />
                            <p className="font-bold">18 Dec</p> {/* Mock Date */}
                        </div>
                    </div>
                </div>
            </div>

            {/* Bottom Section: Footer */}
            <div className="p-4 bg-gray-50 border-t border-gray-100 flex justify-between items-center">
                <p className="text-xs text-gray-400">Present this at reception</p>
                <div className="flex gap-1">
                    {[...Array(5)].map((_, i) => (
                        <div key={i} className="w-1 h-6 bg-gray-300 rounded-full" />
                    ))}
                </div>
            </div>
        </div>
    );
};
