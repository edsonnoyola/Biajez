import React, { useState, useEffect, useRef } from 'react';
import { X } from 'lucide-react';

interface Airport {
    code: string;
    name: string;
    city: string;
    country: string;
}

interface AutocompleteInputProps {
    value: string;
    onChange: (value: string) => void;
    placeholder: string;
    icon?: React.ReactNode;
}

// Popular airports database
const AIRPORTS: Airport[] = [
    { code: 'MEX', name: 'Aeropuerto Internacional Benito Juárez', city: 'Ciudad de México', country: 'México' },
    { code: 'GDL', name: 'Aeropuerto Internacional de Guadalajara', city: 'Guadalajara', country: 'México' },
    { code: 'CUN', name: 'Aeropuerto Internacional de Cancún', city: 'Cancún', country: 'México' },
    { code: 'MTY', name: 'Aeropuerto Internacional de Monterrey', city: 'Monterrey', country: 'México' },
    { code: 'MAD', name: 'Aeropuerto Adolfo Suárez Madrid-Barajas', city: 'Madrid', country: 'España' },
    { code: 'BCN', name: 'Aeropuerto de Barcelona-El Prat', city: 'Barcelona', country: 'España' },
    { code: 'LHR', name: 'London Heathrow Airport', city: 'Londres', country: 'Reino Unido' },
    { code: 'CDG', name: 'Aéroport de Paris-Charles de Gaulle', city: 'París', country: 'Francia' },
    { code: 'JFK', name: 'John F. Kennedy International Airport', city: 'Nueva York', country: 'Estados Unidos' },
    { code: 'LAX', name: 'Los Angeles International Airport', city: 'Los Ángeles', country: 'Estados Unidos' },
    { code: 'MIA', name: 'Miami International Airport', city: 'Miami', country: 'Estados Unidos' },
    { code: 'ORD', name: 'O\'Hare International Airport', city: 'Chicago', country: 'Estados Unidos' },
    { code: 'DFW', name: 'Dallas/Fort Worth International Airport', city: 'Dallas', country: 'Estados Unidos' },
    { code: 'IAH', name: 'George Bush Intercontinental Airport', city: 'Houston', country: 'Estados Unidos' },
    { code: 'ATL', name: 'Hartsfield-Jackson Atlanta International Airport', city: 'Atlanta', country: 'Estados Unidos' },
    { code: 'FRA', name: 'Frankfurt Airport', city: 'Frankfurt', country: 'Alemania' },
    { code: 'AMS', name: 'Amsterdam Airport Schiphol', city: 'Ámsterdam', country: 'Países Bajos' },
    { code: 'FCO', name: 'Leonardo da Vinci–Fiumicino Airport', city: 'Roma', country: 'Italia' },
    { code: 'LIS', name: 'Lisbon Portela Airport', city: 'Lisboa', country: 'Portugal' },
    { code: 'BOG', name: 'El Dorado International Airport', city: 'Bogotá', country: 'Colombia' },
    { code: 'LIM', name: 'Jorge Chávez International Airport', city: 'Lima', country: 'Perú' },
    { code: 'GRU', name: 'São Paulo/Guarulhos International Airport', city: 'São Paulo', country: 'Brasil' },
    { code: 'EZE', name: 'Ministro Pistarini International Airport', city: 'Buenos Aires', country: 'Argentina' },
];

export const AutocompleteInput: React.FC<AutocompleteInputProps> = ({
    value,
    onChange,
    placeholder,
    icon
}) => {
    const [isOpen, setIsOpen] = useState(false);
    const [filteredAirports, setFilteredAirports] = useState<Airport[]>([]);
    const wrapperRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (value.length >= 2) {
            const query = value.toLowerCase();
            const filtered = AIRPORTS.filter(airport =>
                airport.code.toLowerCase().includes(query) ||
                airport.city.toLowerCase().includes(query) ||
                airport.name.toLowerCase().includes(query) ||
                airport.country.toLowerCase().includes(query)
            ).slice(0, 8); // Limit to 8 results

            setFilteredAirports(filtered);
            setIsOpen(filtered.length > 0);
        } else {
            setFilteredAirports([]);
            setIsOpen(false);
        }
    }, [value]);

    // Close dropdown when clicking outside
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) {
                setIsOpen(false);
            }
        };

        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    const handleSelect = (airport: Airport) => {
        onChange(airport.code);
        setIsOpen(false);
    };

    const handleClear = () => {
        onChange('');
        setIsOpen(false);
    };

    return (
        <div ref={wrapperRef} className="relative w-full">
            <div className="relative">
                {icon && (
                    <div className="absolute left-3 top-3 text-gray-400">
                        {icon}
                    </div>
                )}
                <input
                    type="text"
                    value={value}
                    onChange={(e) => onChange(e.target.value.toUpperCase())}
                    onFocus={() => value.length >= 2 && setIsOpen(filteredAirports.length > 0)}
                    placeholder={placeholder}
                    className={`glass-input w-full ${icon ? 'pl-10' : 'pl-4'} pr-10 transition-all duration-200 ${isOpen ? 'rounded-b-none border-b-0' : ''
                        }`}
                />
                {value && (
                    <button
                        type="button"
                        onClick={handleClear}
                        className="absolute right-3 top-3 text-gray-400 hover:text-white transition-colors"
                    >
                        <X size={18} />
                    </button>
                )}
            </div>

            {isOpen && filteredAirports.length > 0 && (
                <div className="absolute z-50 w-full bg-gray-900/95 backdrop-blur-xl border border-white/10 border-t-0 rounded-b-xl shadow-2xl max-h-64 overflow-y-auto">
                    {filteredAirports.map((airport) => (
                        <button
                            key={airport.code}
                            type="button"
                            onClick={() => handleSelect(airport)}
                            className="w-full px-4 py-3 text-left hover:bg-primary/20 transition-colors border-b border-white/5 last:border-b-0 focus:bg-primary/30 focus:outline-none"
                        >
                            <div className="flex items-center justify-between">
                                <div className="flex-1">
                                    <div className="flex items-center gap-2">
                                        <span className="font-bold text-primary">{airport.code}</span>
                                        <span className="text-sm text-gray-400">•</span>
                                        <span className="text-sm text-white">{airport.city}</span>
                                    </div>
                                    <div className="text-xs text-gray-500 mt-0.5 line-clamp-1">
                                        {airport.name}
                                    </div>
                                </div>
                                <div className="text-xs text-gray-600 ml-2">
                                    {airport.country}
                                </div>
                            </div>
                        </button>
                    ))}
                </div>
            )}
        </div>
    );
};
