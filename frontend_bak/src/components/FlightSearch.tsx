import React, { useState } from 'react';
import { Plane, Calendar, MapPin, Search } from 'lucide-react';
import axios from 'axios';

interface FlightSearchProps {
    onSearch: (results: any[]) => void;
}

export const FlightSearch: React.FC<FlightSearchProps> = ({ onSearch }) => {
    const [origin, setOrigin] = useState('');
    const [dest, setDest] = useState('');
    const [date, setDate] = useState('');
    const [isLoading, setIsLoading] = useState(false);

    const handleSearch = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsLoading(true);
        try {
            const response = await axios.get('http://localhost:8000/v1/search', {
                params: { origin, destination: dest, date }
            });
            onSearch(response.data);
        } catch (error) {
            console.error("Search failed", error);
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="glass-panel p-6 mb-8">
            <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
                <Plane className="text-primary" />
                Find Flights
            </h2>

            <form onSubmit={handleSearch} className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="relative">
                    <MapPin className="absolute left-3 top-3 text-gray-500" size={18} />
                    <input
                        type="text"
                        placeholder="Origin (e.g. JFK)"
                        value={origin}
                        onChange={e => setOrigin(e.target.value.toUpperCase())}
                        className="glass-input w-full pl-10"
                        required
                    />
                </div>

                <div className="relative">
                    <MapPin className="absolute left-3 top-3 text-gray-500" size={18} />
                    <input
                        type="text"
                        placeholder="Destination (e.g. LHR)"
                        value={dest}
                        onChange={e => setDest(e.target.value.toUpperCase())}
                        className="glass-input w-full pl-10"
                        required
                    />
                </div>

                <div className="relative">
                    <Calendar className="absolute left-3 top-3 text-gray-500" size={18} />
                    <input
                        type="date"
                        value={date}
                        onChange={e => setDate(e.target.value)}
                        className="glass-input w-full pl-10"
                        required
                    />
                </div>

                <button
                    type="submit"
                    disabled={isLoading}
                    className="glass-button bg-primary text-white hover:bg-primary/90 flex items-center justify-center gap-2"
                >
                    {isLoading ? 'Searching...' : <><Search size={18} /> Search</>}
                </button>
            </form>
        </div>
    );
};
