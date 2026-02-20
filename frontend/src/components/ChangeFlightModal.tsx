import React, { useState } from 'react';
import { X, Plane, Calendar, MapPin, AlertCircle, ArrowRight } from 'lucide-react';
import axios from 'axios';
import API_URL from '../config/api';

interface ChangeFlightModalProps {
    isOpen: boolean;
    onClose: () => void;
    orderId: string;
    currentTrip: {
        origin: string;
        destination: string;
        departure_date: string;
        pnr: string;
    };
    userId: string;
}

interface ChangeOffer {
    id: string;
    change_total_amount: string;
    change_total_currency: string;
    new_total_amount: string;
    new_total_currency: string;
    penalty_total_amount: string;
    penalty_total_currency: string;
    expires_at: string;
    slices: {
        add: Array<{
            segments: Array<{
                origin: { iata_code: string; name: string };
                destination: { iata_code: string; name: string };
                departing_at: string;
                arriving_at: string;
                operating_carrier: { name: string; iata_code: string };
                duration: string;
            }>;
        }>;
    };
}

export const ChangeFlightModal: React.FC<ChangeFlightModalProps> = ({
    isOpen,
    onClose,
    orderId,
    currentTrip,
    userId
}) => {
    const [step, setStep] = useState<'form' | 'offers' | 'confirm'>('form');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Form state
    const [newOrigin, setNewOrigin] = useState(currentTrip.origin);
    const [newDestination, setNewDestination] = useState(currentTrip.destination);
    const [newDate, setNewDate] = useState(currentTrip.departure_date);
    const [cabinClass, setCabinClass] = useState('economy');

    // Offers state
    const [offers, setOffers] = useState<ChangeOffer[]>([]);
    const [selectedOffer, setSelectedOffer] = useState<ChangeOffer | null>(null);

    const handleSearchChanges = async () => {
        setLoading(true);
        setError(null);

        try {
            // First, get the current order details to find slice IDs
            const orderDetails = await axios.get(`${API_URL}/v1/orders/detail/${orderId}`);
            const sliceId = orderDetails.data.slices?.[0]?.id;

            if (!sliceId) {
                throw new Error("Could not find slice ID from order");
            }

            // Create change request - send body as JSON, order_id and user_id as query params
            const response = await axios.post(`${API_URL}/v1/orders/change-request`, {
                slices_to_remove: [{ slice_id: sliceId }],
                slices_to_add: [{
                    origin: newOrigin,
                    destination: newDestination,
                    departure_date: newDate,
                    cabin_class: cabinClass
                }]
            }, {
                params: {
                    order_id: orderId,
                    user_id: userId
                }
            });

            setOffers(response.data.order_change_offers || []);

            if (response.data.order_change_offers?.length > 0) {
                setStep('offers');
            } else {
                setError('No change options available for this flight. The airline may not allow changes.');
            }
        } catch (e: any) {
            console.error('Error creating change request:', e);
            setError(e.response?.data?.detail || 'Failed to search for flight changes');
        } finally {
            setLoading(false);
        }
    };

    const handleConfirmChange = async () => {
        if (!selectedOffer) return;

        setLoading(true);
        setError(null);

        try {
            await axios.post(`${API_URL}/v1/orders/change-confirm/${selectedOffer.id}`, null, {
                params: {
                    user_id: userId,
                    payment_amount: parseFloat(selectedOffer.change_total_amount)
                }
            });

            alert('Flight changed successfully! ✈️');
            onClose();
            window.location.reload(); // Refresh to show updated trip
        } catch (e: any) {
            console.error('Error confirming change:', e);
            setError(e.response?.data?.detail || 'Failed to confirm flight change');
        } finally {
            setLoading(false);
        }
    };

    const formatDateTime = (isoString: string) => {
        return new Date(isoString).toLocaleString('en-US', {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
            <div className="bg-gray-900/95 backdrop-blur-xl border border-white/10 w-full max-w-4xl rounded-3xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200 flex flex-col max-h-[90vh]">

                {/* Header */}
                <div className="bg-gradient-to-r from-blue-900 to-gray-900 p-6 text-white relative flex items-center justify-between border-b border-white/5">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-blue-500/20 flex items-center justify-center text-blue-400">
                            <Plane size={20} />
                        </div>
                        <div>
                            <h2 className="text-xl font-bold">Change Flight</h2>
                            <p className="text-sm text-gray-400">PNR: {currentTrip.pnr}</p>
                        </div>
                    </div>
                    <button onClick={onClose} className="p-2 hover:bg-white/10 rounded-full transition-colors">
                        <X size={20} />
                    </button>
                </div>

                {/* Content */}
                <div className="p-6 overflow-y-auto custom-scrollbar flex-1">
                    {error && (
                        <div className="mb-4 p-4 bg-red-500/10 border border-red-500/20 rounded-lg flex items-start gap-3">
                            <AlertCircle className="text-red-400 flex-shrink-0 mt-0.5" size={20} />
                            <p className="text-red-400 text-sm">{error}</p>
                        </div>
                    )}

                    {/* Step 1: Search Form */}
                    {step === 'form' && (
                        <div className="space-y-6">
                            <div className="bg-white/5 border border-white/10 rounded-xl p-4">
                                <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                                    <MapPin size={18} className="text-blue-400" />
                                    Current Flight
                                </h3>
                                <div className="flex items-center gap-4 text-gray-300">
                                    <span className="font-mono text-xl">{currentTrip.origin}</span>
                                    <ArrowRight className="text-gray-500" size={20} />
                                    <span className="font-mono text-xl">{currentTrip.destination}</span>
                                    <span className="text-gray-500">•</span>
                                    <span>{new Date(currentTrip.departure_date).toLocaleDateString()}</span>
                                </div>
                            </div>

                            <div className="bg-white/5 border border-white/10 rounded-xl p-6">
                                <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                                    <Calendar size={18} className="text-green-400" />
                                    New Flight Details
                                </h3>

                                <div className="grid grid-cols-2 gap-4">
                                    <div>
                                        <label className="block text-sm text-gray-400 mb-2">Origin</label>
                                        <input
                                            type="text"
                                            value={newOrigin}
                                            onChange={(e) => setNewOrigin(e.target.value.toUpperCase())}
                                            className="glass-input w-full"
                                            placeholder="MEX"
                                            maxLength={3}
                                        />
                                    </div>
                                    <div>
                                        <label className="block text-sm text-gray-400 mb-2">Destination</label>
                                        <input
                                            type="text"
                                            value={newDestination}
                                            onChange={(e) => setNewDestination(e.target.value.toUpperCase())}
                                            className="glass-input w-full"
                                            placeholder="CUN"
                                            maxLength={3}
                                        />
                                    </div>
                                    <div>
                                        <label className="block text-sm text-gray-400 mb-2">Departure Date</label>
                                        <input
                                            type="date"
                                            value={newDate}
                                            onChange={(e) => setNewDate(e.target.value)}
                                            className="glass-input w-full"
                                        />
                                    </div>
                                    <div>
                                        <label className="block text-sm text-gray-400 mb-2">Cabin Class</label>
                                        <select
                                            value={cabinClass}
                                            onChange={(e) => setCabinClass(e.target.value)}
                                            className="glass-input w-full bg-black/20"
                                        >
                                            <option value="economy">Economy</option>
                                            <option value="premium_economy">Premium Economy</option>
                                            <option value="business">Business</option>
                                            <option value="first">First</option>
                                        </select>
                                    </div>
                                </div>
                            </div>

                            <button
                                onClick={handleSearchChanges}
                                disabled={loading}
                                className="w-full py-3 bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 text-white rounded-xl font-semibold transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                {loading ? 'Searching...' : 'Search Change Options'}
                            </button>
                        </div>
                    )}

                    {/* Step 2: Offers */}
                    {step === 'offers' && (
                        <div className="space-y-4">
                            <h3 className="text-lg font-semibold mb-4">Available Change Options</h3>

                            {offers.map((offer) => (
                                <div
                                    key={offer.id}
                                    onClick={() => setSelectedOffer(offer)}
                                    className={`bg-white/5 border rounded-xl p-4 cursor-pointer transition-all ${selectedOffer?.id === offer.id
                                        ? 'border-blue-500 bg-blue-500/10'
                                        : 'border-white/10 hover:border-white/20'
                                        }`}
                                >
                                    {/* Flight Details */}
                                    {offer.slices.add.map((slice, idx) => (
                                        <div key={idx} className="mb-4">
                                            {slice.segments.map((seg, segIdx) => (
                                                <div key={segIdx} className="flex items-center justify-between mb-2">
                                                    <div className="flex items-center gap-4">
                                                        <span className="font-mono text-lg">{seg.origin.iata_code}</span>
                                                        <ArrowRight className="text-gray-500" size={16} />
                                                        <span className="font-mono text-lg">{seg.destination.iata_code}</span>
                                                        <span className="text-sm text-gray-400">
                                                            {seg.operating_carrier.name}
                                                        </span>
                                                    </div>
                                                    <span className="text-sm text-gray-400">
                                                        {formatDateTime(seg.departing_at)}
                                                    </span>
                                                </div>
                                            ))}
                                        </div>
                                    ))}

                                    {/* Pricing */}
                                    <div className="border-t border-white/10 pt-4 grid grid-cols-3 gap-4 text-sm">
                                        <div>
                                            <p className="text-gray-400">Change Fee</p>
                                            <p className="text-lg font-semibold text-yellow-400">
                                                {offer.change_total_currency} ${offer.change_total_amount}
                                            </p>
                                        </div>
                                        <div>
                                            <p className="text-gray-400">Penalty</p>
                                            <p className="text-lg font-semibold text-red-400">
                                                {offer.penalty_total_currency} ${offer.penalty_total_amount}
                                            </p>
                                        </div>
                                        <div>
                                            <p className="text-gray-400">New Total</p>
                                            <p className="text-lg font-semibold text-green-400">
                                                {offer.new_total_currency} ${offer.new_total_amount}
                                            </p>
                                        </div>
                                    </div>
                                </div>
                            ))}

                            <div className="flex gap-3 mt-6">
                                <button
                                    onClick={() => setStep('form')}
                                    className="flex-1 py-3 bg-gray-700 hover:bg-gray-600 text-white rounded-xl font-semibold transition-all"
                                >
                                    Back
                                </button>
                                <button
                                    onClick={handleConfirmChange}
                                    disabled={!selectedOffer || loading}
                                    className="flex-1 py-3 bg-gradient-to-r from-green-600 to-green-700 hover:from-green-700 hover:to-green-800 text-white rounded-xl font-semibold transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                    {loading ? 'Processing...' : 'Confirm Change'}
                                </button>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};
