import React from 'react';
import { MapPin, Star, Wifi, Coffee, UtensilsCrossed, Dumbbell, ParkingCircle, Users } from 'lucide-react';

interface HotelOffer {
    name: string;
    hotelId: string;
    rating: string;
    address: {
        cityName: string;
        countryCode: string;
    };
    price: {
        total: string;
        currency: string;
    };
    cancellation_policy?: {
        refundable: boolean;
        free_cancellation_until?: string;
    };
}

interface HotelCardProps {
    hotel: HotelOffer;
    onBook: (offerId: string, amount: number) => void;
}

// Mock hotel images - in production, this would come from API
const getHotelImage = (hotelId: string) => {
    const images = [
        'https://images.unsplash.com/photo-1566073771259-6a8506099945?w=400&h=300&fit=crop',
        'https://images.unsplash.com/photo-1542314831-068cd1dbfeeb?w=400&h=300&fit=crop',
        'https://images.unsplash.com/photo-1445019980597-93fa8acb246c?w=400&h=300&fit=crop',
    ];
    const index = parseInt(hotelId.slice(-1), 16) % images.length;
    return images[index];
};

// Mock amenities - in production, this would come from API
const getMockAmenities = (rating: string) => {
    const baseAmenities = [
        { icon: Wifi, label: 'WiFi Gratis', color: 'blue' },
        { icon: Coffee, label: 'Desayuno', color: 'amber' },
    ];

    if (parseInt(rating) >= 4) {
        baseAmenities.push(
            { icon: Dumbbell, label: 'Gym', color: 'red' },
            { icon: UtensilsCrossed, label: 'Restaurante', color: 'green' }
        );
    }

    if (parseInt(rating) >= 5) {
        baseAmenities.push(
            { icon: ParkingCircle, label: 'Parking', color: 'purple' }
        );
    }

    return baseAmenities;
};

const colorMap: Record<string, string> = {
    blue: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    amber: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
    red: 'bg-red-500/20 text-red-400 border-red-500/30',
    green: 'bg-green-500/20 text-green-400 border-green-500/30',
    purple: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
};

export const HotelCard: React.FC<HotelCardProps> = ({ hotel, onBook }) => {
    const amenities = getMockAmenities(hotel.rating);
    const price = parseFloat(hotel.price.total);
    const isGreatDeal = price < 150;

    return (
        <div className="group relative bg-gradient-to-br from-gray-900/95 to-gray-800/95 backdrop-blur-xl border border-white/10 rounded-2xl overflow-hidden hover:border-primary/50 hover:shadow-2xl hover:shadow-primary/10 transition-all duration-300 w-full cursor-pointer">
            {/* Background Gradient Effect */}
            <div className="absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-accent/5 opacity-0 group-hover:opacity-100 transition-opacity duration-500" />

            {/* Great Deal Badge */}
            {isGreatDeal && (
                <div className="absolute -right-8 top-6 bg-gradient-to-r from-green-500 to-emerald-600 text-white text-xs font-bold px-8 py-1 rotate-45 shadow-lg z-20">
                    Oferta
                </div>
            )}

            {/* Hotel Image */}
            <div className="relative h-40 sm:h-48 overflow-hidden">
                <img
                    src={getHotelImage(hotel.hotelId)}
                    alt={hotel.name}
                    className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-500"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-gray-900 via-transparent to-transparent" />

                {/* Rating Badge on Image */}
                <div className="absolute top-3 left-3 bg-gray-900/90 backdrop-blur-sm px-3 py-1.5 rounded-lg flex items-center gap-1.5 border border-white/10">
                    <Star size={14} className="text-yellow-400 fill-yellow-400" />
                    <span className="text-sm font-bold text-white">{hotel.rating}</span>
                    <span className="text-xs text-gray-400">Estrellas</span>
                </div>

                {/* Cancellation Policy Badge */}
                {hotel.cancellation_policy?.refundable && (
                    <div className="absolute top-3 right-3 bg-green-500/90 backdrop-blur-sm px-3 py-1.5 rounded-lg flex items-center gap-1.5 border border-green-400/30">
                        <span className="text-xs font-bold text-white">✅ Cancelación gratis</span>
                        {hotel.cancellation_policy.free_cancellation_until && (
                            <span className="text-xs text-green-100">hasta {new Date(hotel.cancellation_policy.free_cancellation_until).toLocaleDateString('es-MX', { month: 'short', day: 'numeric' })}</span>
                        )}
                    </div>
                )}
            </div>

            {/* Content */}
            <div className="relative z-10 p-4 space-y-3">
                {/* Hotel Name & Location */}
                <div>
                    <h3 className="font-bold text-lg text-white line-clamp-1 mb-1 group-hover:text-primary transition-colors">
                        {hotel.name}
                    </h3>
                    <div className="flex items-center gap-1.5 text-gray-400 text-xs">
                        <MapPin size={12} className="flex-shrink-0" />
                        <span className="line-clamp-1">{hotel.address.cityName}, {hotel.address.countryCode}</span>
                    </div>
                </div>

                {/* Amenities */}
                <div className="flex flex-wrap gap-1.5">
                    {amenities.slice(0, 4).map((amenity, idx) => {
                        const Icon = amenity.icon;
                        return (
                            <span
                                key={idx}
                                className={`flex items-center gap-1 text-[10px] px-2 py-1 rounded-md border ${colorMap[amenity.color]}`}
                            >
                                <Icon size={10} />
                                {amenity.label}
                            </span>
                        );
                    })}
                    {amenities.length > 4 && (
                        <span className="flex items-center gap-1 text-[10px] px-2 py-1 rounded-md border bg-gray-500/20 text-gray-400 border-gray-500/30">
                            +{amenities.length - 4} más
                        </span>
                    )}
                </div>

                {/* Price & CTA */}
                <div className="flex items-end justify-between pt-3 border-t border-white/10">
                    <div>
                        <p className="text-xs text-gray-500 mb-0.5">Desde</p>
                        <div className="flex items-baseline gap-1">
                            <span className="text-xs text-gray-400">$</span>
                            <p className="text-2xl font-bold bg-gradient-to-r from-accent via-primary to-accent bg-clip-text text-transparent">
                                {hotel.price.total}
                            </p>
                        </div>
                        <p className="text-[10px] text-gray-500">{hotel.price.currency} / noche</p>
                    </div>

                    <button
                        onClick={() => onBook(hotel.hotelId, parseFloat(hotel.price.total))}
                        className="bg-gradient-to-r from-primary to-accent hover:from-primary/90 hover:to-accent/90 text-white text-sm font-bold px-5 py-2.5 rounded-xl transition-all duration-200 shadow-lg shadow-primary/25 hover:shadow-primary/40 hover:scale-105 active:scale-95"
                    >
                        Ver Habitaciones
                    </button>
                </div>
            </div>
        </div>
    );
};
