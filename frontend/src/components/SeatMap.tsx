import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Loader2 } from 'lucide-react';
import { cn } from '../lib/utils';

interface SeatMapProps {
    offerId: string;
    onSelect: (seat: any) => void;
    seatPreference?: string; // WINDOW, MIDDLE, AISLE
    positionPreference?: string; // TOP, MIDDLE, BOTTOM
}

export const SeatMap: React.FC<SeatMapProps> = ({ offerId, onSelect, seatPreference = 'WINDOW', positionPreference = 'MIDDLE' }) => {
    const [loading, setLoading] = useState(true);
    const [maps, setMaps] = useState<any[]>([]);
    const [selectedSeat, setSelectedSeat] = useState<string | null>(null);
    const [autoSelected, setAutoSelected] = useState(false);

    useEffect(() => {
        const fetchSeats = async () => {
            try {
                const res = await axios.get(`http://localhost:8000/v1/seats/${offerId}`);
                setMaps(res.data.maps);
            } catch (e) {
                console.error("Failed to fetch seats", e);
            } finally {
                setLoading(false);
            }
        };
        fetchSeats();
    }, [offerId]);

    // Auto-select seat based on preferences
    useEffect(() => {
        if (!maps || maps.length === 0 || autoSelected) return;

        const cabin = maps[0]?.cabins?.[0];
        if (!cabin) return;

        // Determine target row based on position preference
        const totalRows = cabin.rows.length;
        let targetRowIndex = Math.floor(totalRows / 2); // MIDDLE by default

        if (positionPreference === 'TOP') {
            targetRowIndex = Math.floor(totalRows * 0.25); // First quarter
        } else if (positionPreference === 'BOTTOM') {
            targetRowIndex = Math.floor(totalRows * 0.75); // Last quarter
        }

        // Find best matching seat
        for (let i = Math.max(0, targetRowIndex - 2); i < Math.min(totalRows, targetRowIndex + 3); i++) {
            const row = cabin.rows[i];
            if (!row) continue;

            for (const section of row.sections) {
                for (const el of section.elements) {
                    if (el.type !== 'seat') continue;

                    // Check if seat matches preference
                    const letter = el.designator.replace(/[0-9]/g, '');
                    let matches = false;

                    if (seatPreference === 'WINDOW') {
                        matches = ['A', 'F'].includes(letter); // Common window seats
                    } else if (seatPreference === 'AISLE') {
                        matches = ['C', 'D'].includes(letter); // Common aisle seats
                    } else if (seatPreference === 'MIDDLE') {
                        matches = ['B', 'E'].includes(letter); // Common middle seats
                    }

                    if (matches) {
                        // Auto-select this seat
                        handleSeatClick(el);
                        setAutoSelected(true);
                        return;
                    }
                }
            }
        }
    }, [maps, seatPreference, positionPreference, autoSelected]);

    const handleSeatClick = (element: any) => {
        if (element.type !== 'seat') return;
        if (element.available_services?.length === 0 && !element.disclosures) return; // Unavailable?
        // Actually Duffel returns 'available_services' for paid seats.
        // If it's free, it might not have services but is still selectable if not occupied.
        // For simplicity, we assume all visible seats are selectable.

        setSelectedSeat(element.designator);

        // Find price
        let price = 0;
        let currency = "USD";
        let serviceId = null;

        if (element.available_services && element.available_services.length > 0) {
            price = parseFloat(element.available_services[0].total_amount);
            currency = element.available_services[0].total_currency;
            serviceId = element.available_services[0].id;
        }

        onSelect({
            designator: element.designator,
            price,
            currency,
            serviceId
        });
    };

    if (loading) return <div className="flex justify-center p-8"><Loader2 className="animate-spin" /></div>;
    if (!maps || maps.length === 0) return <div className="text-center p-8 text-gray-400">Seat map not available for this flight.</div>;

    // Render first segment only for demo
    const cabin = maps[0].cabins[0]; // First cabin

    return (
        <div className="w-full overflow-x-auto">
            <div className="flex flex-col gap-2 min-w-[300px] p-4 items-center">
                {/* Cockpit Indicator */}
                <div className="w-16 h-8 bg-gray-200 rounded-t-full mb-4 opacity-20" />

                {cabin.rows.map((row: any, i: number) => (
                    <div key={i} className="flex gap-4 items-center">
                        <span className="text-xs text-gray-400 w-4 text-center">{i + 1}</span>
                        <div className="flex gap-1">
                            {row.sections.map((section: any, secIdx: number) => (
                                <div key={secIdx} className="flex gap-1">
                                    {section.elements.map((el: any, elIdx: number) => {
                                        if (el.type !== 'seat') return <div key={elIdx} className="w-8" />; // Aisle

                                        const isPaid = el.available_services && el.available_services.length > 0;
                                        const isSelected = selectedSeat === el.designator;

                                        return (
                                            <button
                                                key={elIdx}
                                                onClick={() => handleSeatClick(el)}
                                                className={cn(
                                                    "w-8 h-8 rounded-md flex items-center justify-center transition-all text-xs font-bold relative group",
                                                    isSelected
                                                        ? "bg-green-500 text-white shadow-lg scale-110"
                                                        : isPaid
                                                            ? "bg-amber-100 text-amber-700 border border-amber-200 hover:bg-amber-200"
                                                            : "bg-blue-50 text-blue-600 border border-blue-100 hover:bg-blue-100"
                                                )}
                                            >
                                                {el.designator.replace(/[0-9]/g, '')}
                                                {isPaid && (
                                                    <span className="absolute -top-8 left-1/2 -translate-x-1/2 bg-black text-white text-[10px] px-2 py-1 rounded opacity-0 group-hover:opacity-100 whitespace-nowrap z-10 pointer-events-none">
                                                        ${el.available_services[0].total_amount}
                                                    </span>
                                                )}
                                            </button>
                                        );
                                    })}
                                    {/* Spacer between sections */}
                                    {secIdx < row.sections.length - 1 && <div className="w-4" />}
                                </div>
                            ))}
                        </div>
                    </div>
                ))}
            </div>

            <div className="flex gap-4 justify-center mt-4 text-xs text-gray-500">
                <div className="flex items-center gap-1"><div className="w-3 h-3 bg-blue-50 border border-blue-100 rounded" /> Free</div>
                <div className="flex items-center gap-1"><div className="w-3 h-3 bg-amber-100 border border-amber-200 rounded" /> Paid</div>
                <div className="flex items-center gap-1"><div className="w-3 h-3 bg-green-500 rounded" /> Selected</div>
            </div>
        </div>
    );
};
