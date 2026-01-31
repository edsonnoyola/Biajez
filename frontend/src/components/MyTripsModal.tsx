import React, { useState, useEffect } from 'react';
import { X, Plane, AlertCircle, CheckCircle, RefreshCw, Wallet } from 'lucide-react';
import axios from 'axios';
import { ChangeFlightModal } from './ChangeFlightModal';
import { CreditsModal } from './CreditsModal';
import API_URL from '../config/api';

interface MyTripsModalProps {
    isOpen: boolean;
    onClose: () => void;
}

interface Trip {
    id?: string;
    booking_reference: string;
    provider_source: string;
    total_amount: number;
    status: 'TICKETED' | 'CONFIRMED' | 'CANCELLED';
    invoice_url: string;
    duffel_order_id?: string;
    departure_city?: string;
    arrival_city?: string;
    departure_date?: string;
    pnr?: string;
    booking_type?: string;
    hotel_name?: string;
    check_in_date?: string;
    check_out_date?: string;
    ticket_url?: string;
}

export const MyTripsModal: React.FC<MyTripsModalProps> = ({ isOpen, onClose }) => {
    const [trips, setTrips] = useState<Trip[]>([]);
    const [loading, setLoading] = useState(false);
    const [changeModalOpen, setChangeModalOpen] = useState(false);
    const [creditsModalOpen, setCreditsModalOpen] = useState(false);
    const [ticketModalOpen, setTicketModalOpen] = useState(false);
    const [selectedTrip, setSelectedTrip] = useState<Trip | null>(null);

    useEffect(() => {
        if (isOpen) {
            fetchTrips();
        }
    }, [isOpen]);

    const fetchTrips = async () => {
        setLoading(true);
        try {
            const res = await axios.get(`${API_URL}/v1/trips/demo-user`);
            setTrips(res.data);
        } catch (e) {
            console.error("Failed to fetch trips", e);
        } finally {
            setLoading(false);
        }
    };

    const handleCancel = async (pnr: string) => {
        if (!confirm("Are you sure you want to cancel this trip?")) return;
        try {
            await axios.post(`${API_URL}/v1/trips/${pnr}/cancel`);
            fetchTrips(); // Refresh
            alert("Trip cancelled successfully!");
        } catch (e) {
            alert("Failed to cancel trip");
        }
    };

    const handleOpenChangeModal = (trip: Trip) => {
        setSelectedTrip(trip);
        setChangeModalOpen(true);
    };



    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
            <div className="bg-gray-900/95 backdrop-blur-xl border border-white/10 w-full max-w-2xl rounded-3xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200 flex flex-col max-h-[80vh]">

                {/* Header */}
                <div className="bg-gradient-to-r from-blue-900 to-gray-900 p-6 text-white relative flex items-center justify-between border-b border-white/5">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-blue-500/20 flex items-center justify-center text-blue-400">
                            <Plane size={20} />
                        </div>
                        <h2 className="text-xl font-bold">My Trips</h2>
                    </div>
                    <div className="flex items-center gap-2">
                        <button
                            onClick={() => setCreditsModalOpen(true)}
                            className="px-4 py-2 bg-green-500/10 hover:bg-green-500/20 text-green-400 rounded-lg text-sm font-medium transition-colors border border-green-500/20 flex items-center gap-2"
                        >
                            <Wallet size={16} />
                            My Credits
                        </button>
                        <button onClick={onClose} className="p-2 hover:bg-white/10 rounded-full transition-colors">
                            <X size={20} />
                        </button>
                    </div>
                </div>

                {/* Content */}
                <div className="p-6 overflow-y-auto space-y-4 custom-scrollbar flex-1">
                    {loading ? (
                        <div className="text-center text-gray-400 py-10">Loading trips...</div>
                    ) : trips.length === 0 ? (
                        <div className="text-center text-gray-400 py-10">
                            <p>No trips found.</p>
                            <button onClick={onClose} className="mt-4 text-primary hover:underline">Book a flight</button>
                        </div>
                    ) : (
                        trips.map((trip) => (
                            <div key={trip.booking_reference} className="bg-white/5 border border-white/5 rounded-xl p-4 flex flex-col md:flex-row justify-between items-center gap-4">
                                <div className="flex items-center gap-4">
                                    <div className={`w-12 h-12 rounded-full flex items-center justify-center ${trip.status === 'CANCELLED' ? 'bg-red-500/20 text-red-500' : 'bg-green-500/20 text-green-500'}`}>
                                        {trip.status === 'CANCELLED' ? <AlertCircle size={24} /> : <CheckCircle size={24} />}
                                    </div>
                                    <div>
                                        <p className="font-bold text-lg">PNR: {trip.booking_reference}</p>
                                        <p className="text-sm text-gray-400">{trip.provider_source} • ${trip.total_amount}</p>
                                        <span className={`text-xs px-2 py-0.5 rounded-full mt-1 inline-block ${trip.status === 'CANCELLED' ? 'bg-red-500/10 text-red-400' : 'bg-green-500/10 text-green-400'}`}>
                                            {trip.status}
                                        </span>
                                    </div>
                                </div>

                                {trip.status !== 'CANCELLED' && (
                                    <div className="flex gap-2">
                                        <button
                                            onClick={() => {
                                                setSelectedTrip(trip);
                                                setTicketModalOpen(true);
                                            }}
                                            className="px-4 py-2 bg-green-500/10 hover:bg-green-500/20 text-green-400 rounded-lg text-sm font-medium transition-colors border border-green-500/20 flex items-center gap-2"
                                        >
                                            <CheckCircle size={16} />
                                            View Ticket
                                        </button>
                                        <button
                                            onClick={() => handleOpenChangeModal(trip)}
                                            className="px-4 py-2 bg-blue-500/10 hover:bg-blue-500/20 text-blue-400 rounded-lg text-sm font-medium transition-colors border border-blue-500/20 flex items-center gap-2"
                                        >
                                            <RefreshCw size={16} />
                                            Change Flight
                                        </button>
                                        <button
                                            onClick={() => handleCancel(trip.booking_reference)}
                                            className="px-4 py-2 bg-red-500/10 hover:bg-red-500/20 text-red-400 rounded-lg text-sm font-medium transition-colors border border-red-500/20"
                                        >
                                            Cancel Trip
                                        </button>
                                    </div>
                                )}
                            </div>
                        ))
                    )}
                </div>
            </div>

            {/* Change Flight Modal */}
            {selectedTrip && (
                <ChangeFlightModal
                    isOpen={changeModalOpen}
                    onClose={() => {
                        setChangeModalOpen(false);
                        setSelectedTrip(null);
                        fetchTrips();
                    }}
                    orderId={selectedTrip.duffel_order_id || ''}
                    currentTrip={{
                        origin: selectedTrip.departure_city || '',
                        destination: selectedTrip.arrival_city || '',
                        departure_date: selectedTrip.departure_date || '',
                        pnr: selectedTrip.pnr || selectedTrip.booking_reference
                    }}
                    userId="demo-user"
                />
            )}

            {/* Credits Modal */}
            <CreditsModal
                isOpen={creditsModalOpen}
                onClose={() => setCreditsModalOpen(false)}
                userId="demo-user"
            />

            {/* Ticket Modal */}
            {ticketModalOpen && selectedTrip && (
                <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
                    <div className="bg-gray-900/95 backdrop-blur-xl border border-white/10 w-full max-w-4xl max-w-[90vw] rounded-3xl shadow-2xl overflow-hidden">
                        <div className="bg-gradient-to-r from-green-900 to-gray-900 p-6 text-white relative flex items-center justify-between border-b border-white/5">
                            <h2 className="text-xl font-bold">Ticket - {selectedTrip.booking_reference}</h2>
                            <button onClick={() => setTicketModalOpen(false)} className="p-2 hover:bg-white/10 rounded-full transition-colors">
                                <X size={20} />
                            </button>
                        </div>
                        <div className="p-6 bg-white">
                            {selectedTrip.ticket_url ? (
                                <iframe
                                    src={selectedTrip.ticket_url}
                                    className="w-full h-[600px] border-0"
                                    title="Ticket"
                                />
                            ) : (
                                <div className="text-center py-20 text-gray-600">
                                    <p className="text-lg mb-4">Ticket not available</p>
                                    <p className="text-sm">PNR: {selectedTrip.booking_reference}</p>
                                    <p className="text-sm mt-2">Status: {selectedTrip.status}</p>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};
