import React, { useState } from 'react';
import { Plane, Calendar, MapPin, Search, ArrowLeftRight, Clock, Building2 } from 'lucide-react';
import axios from 'axios';
import { AutocompleteInput } from './AutocompleteInput';
import { LoadingSkeleton } from './LoadingSkeleton';

interface FlightSearchProps {
    onSearch: (results: any[]) => void;
}

const AIRLINES = [
    { code: 'ALL', name: 'Todas las aerolíneas' },
    { code: 'AM', name: 'Aeroméxico' },
    { code: 'Y4', name: 'Volaris' },
    { code: 'VB', name: 'VivaAerobus' },
    { code: 'IB', name: 'Iberia' },
    { code: 'BA', name: 'British Airways' },
    { code: 'AA', name: 'American Airlines' },
    { code: 'UA', name: 'United' },
    { code: 'DL', name: 'Delta' },
];

const TIME_SLOTS = [
    { value: 'ANY', label: 'Cualquier hora', icon: '🌍' },
    { value: 'EARLY_MORNING', label: 'Madrugada (0-6h)', icon: '🌅' },
    { value: 'MORNING', label: 'Mañana (6-12h)', icon: '☀️' },
    { value: 'AFTERNOON', label: 'Tarde (12-18h)', icon: '🌤️' },
    { value: 'EVENING', label: 'Noche (18-24h)', icon: '🌙' },
];

const CLASSES = [
    { value: 'ECONOMY', label: 'Economy' },
    { value: 'PREMIUM_ECONOMY', label: 'Premium Economy' },
    { value: 'BUSINESS', label: 'Business' },
    { value: 'FIRST', label: 'First Class' },
];

export const FlightSearch: React.FC<FlightSearchProps> = ({ onSearch }) => {
    const [origin, setOrigin] = useState('');
    const [dest, setDest] = useState('');
    const [date, setDate] = useState('');
    const [returnDate, setReturnDate] = useState('');
    const [isRoundTrip, setIsRoundTrip] = useState(false);
    const [flightClass, setFlightClass] = useState('ECONOMY');
    const [airline, setAirline] = useState('ALL');
    const [timeOfDay, setTimeOfDay] = useState('ANY');
    const [isLoading, setIsLoading] = useState(false);
    const [showAdvanced, setShowAdvanced] = useState(false);

    const handleSearch = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsLoading(true);

        try {
            const params: any = {
                origin,
                destination: dest,
                date,
                cabin: flightClass
            };

            if (isRoundTrip && returnDate) {
                params.return_date = returnDate;
            }

            if (airline !== 'ALL') {
                params.airline = airline;
            }

            if (timeOfDay !== 'ANY') {
                params.time_of_day = timeOfDay;
            }

            const response = await axios.get('http://localhost:8000/v1/search', { params });
            onSearch(response.data);
        } catch (error) {
            console.error("Search failed", error);
        } finally {
            setIsLoading(false);
        }
    };

    const today = new Date().toISOString().split('T')[0];

    return (
        <div className="glass-panel p-6 mb-8">
            <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-semibold flex items-center gap-2">
                    <Plane className="text-primary" />
                    Buscar Vuelos
                </h2>

                {/* Round Trip Toggle */}
                <button
                    type="button"
                    onClick={() => setIsRoundTrip(!isRoundTrip)}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-all ${isRoundTrip
                            ? 'bg-primary/20 text-primary border border-primary/50'
                            : 'bg-gray-800/50 text-gray-400 border border-white/10'
                        }`}
                >
                    <ArrowLeftRight size={16} />
                    <span className="text-sm font-medium">
                        {isRoundTrip ? 'Ida y vuelta' : 'Solo ida'}
                    </span>
                </button>
            </div>

            <form onSubmit={handleSearch} className="space-y-4">
                {/* Origin & Destination Row */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <label className="block text-xs text-gray-400 mb-2">Origen</label>
                        <AutocompleteInput
                            value={origin}
                            onChange={setOrigin}
                            placeholder="Ciudad o código IATA (ej: MEX)"
                            icon={<MapPin size={18} />}
                        />
                    </div>

                    <div>
                        <label className="block text-xs text-gray-400 mb-2">Destino</label>
                        <AutocompleteInput
                            value={dest}
                            onChange={setDest}
                            placeholder="Ciudad o código IATA (ej: MAD)"
                            icon={<MapPin size={18} />}
                        />
                    </div>
                </div>

                {/* Dates Row */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <label className="block text-xs text-gray-400 mb-2">Fecha de salida</label>
                        <div className="relative">
                            <Calendar className="absolute left-3 top-3 text-gray-400" size={18} />
                            <input
                                type="date"
                                value={date}
                                min={today}
                                onChange={e => setDate(e.target.value)}
                                className="glass-input w-full pl-10"
                                required
                            />
                        </div>
                    </div>

                    {isRoundTrip && (
                        <div className="animate-fadeIn">
                            <label className="block text-xs text-gray-400 mb-2">Fecha de regreso</label>
                            <div className="relative">
                                <Calendar className="absolute left-3 top-3 text-gray-400" size={18} />
                                <input
                                    type="date"
                                    value={returnDate}
                                    min={date || today}
                                    onChange={e => setReturnDate(e.target.value)}
                                    className="glass-input w-full pl-10"
                                    required={isRoundTrip}
                                />
                            </div>
                        </div>
                    )}
                </div>

                {/* Advanced Filters Toggle */}
                <button
                    type="button"
                    onClick={() => setShowAdvanced(!showAdvanced)}
                    className="text-sm text-primary hover:text-primary/80 transition-colors flex items-center gap-1"
                >
                    {showAdvanced ? '▼' : '▶'} Filtros avanzados
                </button>

                {/* Advanced Filters */}
                {showAdvanced && (
                    <div className="space-y-4 animate-fadeIn border-t border-white/10 pt-4">
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                            {/* Class Selector */}
                            <div>
                                <label className="block text-xs text-gray-400 mb-2">Clase</label>
                                <select
                                    value={flightClass}
                                    onChange={e => setFlightClass(e.target.value)}
                                    className="glass-input w-full"
                                >
                                    {CLASSES.map(cls => (
                                        <option key={cls.value} value={cls.value}>
                                            {cls.label}
                                        </option>
                                    ))}
                                </select>
                            </div>

                            {/* Airline Filter */}
                            <div>
                                <label className="block text-xs text-gray-400 mb-2">Aerolínea</label>
                                <div className="relative">
                                    <Building2 className="absolute left-3 top-3 text-gray-400" size={18} />
                                    <select
                                        value={airline}
                                        onChange={e => setAirline(e.target.value)}
                                        className="glass-input w-full pl-10"
                                    >
                                        {AIRLINES.map(al => (
                                            <option key={al.code} value={al.code}>
                                                {al.name}
                                            </option>
                                        ))}
                                    </select>
                                </div>
                            </div>

                            {/* Time of Day Filter */}
                            <div>
                                <label className="block text-xs text-gray-400 mb-2">Horario</label>
                                <div className="relative">
                                    <Clock className="absolute left-3 top-3 text-gray-400" size={18} />
                                    <select
                                        value={timeOfDay}
                                        onChange={e => setTimeOfDay(e.target.value)}
                                        className="glass-input w-full pl-10"
                                    >
                                        {TIME_SLOTS.map(slot => (
                                            <option key={slot.value} value={slot.value}>
                                                {slot.icon} {slot.label}
                                            </option>
                                        ))}
                                    </select>
                                </div>
                            </div>
                        </div>
                    </div>
                )}

                {/* Search Button */}
                <button
                    type="submit"
                    disabled={isLoading || !origin || !dest || !date}
                    className="w-full bg-gradient-to-r from-primary to-accent hover:from-primary/90 hover:to-accent/90 disabled:from-gray-700 disabled:to-gray-700 disabled:cursor-not-allowed text-white font-bold py-3 px-6 rounded-xl flex items-center justify-center gap-2 transition-all duration-200 shadow-lg shadow-primary/25 hover:shadow-primary/40 hover:scale-[1.02] active:scale-95"
                >
                    {isLoading ? (
                        <>
                            <div className="animate-spin rounded-full h-5 w-5 border-2 border-white border-t-transparent" />
                            Buscando vuelos...
                        </>
                    ) : (
                        <>
                            <Search size={18} />
                            Buscar vuelos
                        </>
                    )}
                </button>
            </form>

            {/* Loading State */}
            {isLoading && (
                <div className="mt-6 space-y-4">
                    <LoadingSkeleton type="flight" count={3} />
                </div>
            )}
        </div>
    );
};
