import React, { useState, useEffect } from 'react';
import { X, AlertCircle, Check, Plane } from 'lucide-react';
import axios from 'axios';

interface FlightChangeModalProps {
    notificationId: string;
    isOpen: boolean;
    onClose: () => void;
    onActionComplete: () => void;
}

interface FlightDetails {
    departure_time: string;
    arrival_time: string;
    carrier_code: string;
    flight_number: string;
    origin?: string;
    destination?: string;
}

interface ChangeDetails {
    order_id: string;
    original_flight: FlightDetails;
    new_flight: FlightDetails;
    changes: Record<string, any>;
    change_type: string;
}

export const FlightChangeModal: React.FC<FlightChangeModalProps> = ({
    notificationId,
    isOpen,
    onClose,
    onActionComplete
}) => {
    const [changeDetails, setChangeDetails] = useState<ChangeDetails | null>(null);
    const [loading, setLoading] = useState(false);
    const [processing, setProcessing] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (isOpen && notificationId) {
            fetchChangeDetails();
        }
    }, [isOpen, notificationId]);

    const fetchChangeDetails = async () => {
        setLoading(true);
        setError(null);
        try {
            const response = await axios.get(
                `http://localhost:8000/v1/flight-changes/${notificationId}/details`
            );
            setChangeDetails(response.data);
        } catch (err: any) {
            console.error('Error fetching change details:', err);
            setError(err.response?.data?.detail || 'Failed to load change details');
        } finally {
            setLoading(false);
        }
    };

    const handleAccept = async () => {
        setProcessing(true);
        setError(null);
        try {
            await axios.post(
                `http://localhost:8000/v1/flight-changes/${notificationId}/accept`
            );
            onActionComplete();
            onClose();
        } catch (err: any) {
            console.error('Error accepting change:', err);
            setError(err.response?.data?.detail || 'Failed to accept change');
        } finally {
            setProcessing(false);
        }
    };

    const handleReject = async () => {
        if (!confirm('Rejecting this change will cancel your flight and issue a credit. Continue?')) {
            return;
        }

        setProcessing(true);
        setError(null);
        try {
            const response = await axios.post(
                `http://localhost:8000/v1/flight-changes/${notificationId}/reject`
            );
            alert(`Flight cancelled. Credit issued: $${response.data.credit.amount} ${response.data.credit.currency}`);
            onActionComplete();
            onClose();
        } catch (err: any) {
            console.error('Error rejecting change:', err);
            setError(err.response?.data?.detail || 'Failed to reject change');
        } finally {
            setProcessing(false);
        }
    };

    const formatDateTime = (dateString: string) => {
        if (!dateString) return 'N/A';
        const date = new Date(dateString);
        return date.toLocaleString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    };

    const getChangeSummary = () => {
        if (!changeDetails) return [];

        const changes = [];
        const { original_flight, new_flight } = changeDetails;

        if (original_flight.departure_time !== new_flight.departure_time) {
            changes.push({
                field: 'Departure Time',
                old: formatDateTime(original_flight.departure_time),
                new: formatDateTime(new_flight.departure_time)
            });
        }

        if (original_flight.arrival_time !== new_flight.arrival_time) {
            changes.push({
                field: 'Arrival Time',
                old: formatDateTime(original_flight.arrival_time),
                new: formatDateTime(new_flight.arrival_time)
            });
        }

        if (original_flight.flight_number !== new_flight.flight_number) {
            changes.push({
                field: 'Flight Number',
                old: `${original_flight.carrier_code} ${original_flight.flight_number}`,
                new: `${new_flight.carrier_code || original_flight.carrier_code} ${new_flight.flight_number}`
            });
        }

        return changes;
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
            <div className="bg-gradient-to-br from-gray-900 to-gray-800 rounded-2xl shadow-2xl max-w-3xl w-full max-h-[90vh] overflow-hidden border border-white/10">
                {/* Header */}
                <div className="bg-gradient-to-r from-amber-500/20 to-orange-500/20 p-6 border-b border-white/10">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-amber-500/20 rounded-xl">
                                <AlertCircle className="text-amber-400" size={24} />
                            </div>
                            <div>
                                <h2 className="text-2xl font-bold text-white">Flight Change Detected</h2>
                                <p className="text-sm text-gray-400">
                                    The airline has changed your flight. Please review:
                                </p>
                            </div>
                        </div>
                        <button
                            onClick={onClose}
                            className="p-2 hover:bg-white/10 rounded-xl transition-colors"
                            disabled={processing}
                        >
                            <X className="text-gray-400" size={24} />
                        </button>
                    </div>
                </div>

                {/* Content */}
                <div className="p-6 overflow-y-auto max-h-[calc(90vh-200px)]">
                    {loading ? (
                        <div className="flex items-center justify-center py-12">
                            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-amber-400"></div>
                        </div>
                    ) : error ? (
                        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 text-red-400">
                            <p className="font-semibold">Error</p>
                            <p className="text-sm mt-1">{error}</p>
                        </div>
                    ) : changeDetails ? (
                        <div className="space-y-6">
                            {/* Original Flight */}
                            <div className="bg-white/5 border border-white/10 rounded-xl p-4 opacity-60">
                                <div className="flex items-center gap-2 mb-3">
                                    <Plane className="text-gray-400" size={16} />
                                    <span className="text-sm font-semibold text-gray-400 uppercase">
                                        Original Flight
                                    </span>
                                </div>
                                <div className="grid grid-cols-2 gap-4">
                                    <div>
                                        <p className="text-xs text-gray-500">Departure</p>
                                        <p className="text-white font-medium">
                                            {formatDateTime(changeDetails.original_flight.departure_time)}
                                        </p>
                                    </div>
                                    <div>
                                        <p className="text-xs text-gray-500">Arrival</p>
                                        <p className="text-white font-medium">
                                            {formatDateTime(changeDetails.original_flight.arrival_time)}
                                        </p>
                                    </div>
                                    <div>
                                        <p className="text-xs text-gray-500">Flight</p>
                                        <p className="text-white font-medium">
                                            {changeDetails.original_flight.carrier_code} {changeDetails.original_flight.flight_number}
                                        </p>
                                    </div>
                                </div>
                            </div>

                            {/* Arrow */}
                            <div className="flex justify-center">
                                <div className="text-amber-400 font-semibold">↓ CHANGED TO</div>
                            </div>

                            {/* New Flight */}
                            <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-4">
                                <div className="flex items-center gap-2 mb-3">
                                    <Plane className="text-green-400" size={16} />
                                    <span className="text-sm font-semibold text-green-400 uppercase">
                                        New Flight
                                    </span>
                                </div>
                                <div className="grid grid-cols-2 gap-4">
                                    <div>
                                        <p className="text-xs text-gray-400">Departure</p>
                                        <p className="text-white font-medium">
                                            {formatDateTime(changeDetails.new_flight.departure_time || changeDetails.original_flight.departure_time)}
                                        </p>
                                    </div>
                                    <div>
                                        <p className="text-xs text-gray-400">Arrival</p>
                                        <p className="text-white font-medium">
                                            {formatDateTime(changeDetails.new_flight.arrival_time || changeDetails.original_flight.arrival_time)}
                                        </p>
                                    </div>
                                    <div>
                                        <p className="text-xs text-gray-400">Flight</p>
                                        <p className="text-white font-medium">
                                            {changeDetails.new_flight.carrier_code || changeDetails.original_flight.carrier_code}{' '}
                                            {changeDetails.new_flight.flight_number || changeDetails.original_flight.flight_number}
                                        </p>
                                    </div>
                                </div>
                            </div>

                            {/* Changes Summary */}
                            {getChangeSummary().length > 0 && (
                                <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-4">
                                    <div className="flex items-center gap-2 mb-3">
                                        <AlertCircle className="text-amber-400" size={16} />
                                        <span className="text-sm font-semibold text-amber-400 uppercase">
                                            Changes
                                        </span>
                                    </div>
                                    <div className="space-y-2">
                                        {getChangeSummary().map((change, idx) => (
                                            <div key={idx} className="text-sm">
                                                <span className="text-gray-400">{change.field}:</span>
                                                <div className="ml-4 mt-1">
                                                    <span className="text-gray-500 line-through">{change.old}</span>
                                                    <span className="text-amber-400 mx-2">→</span>
                                                    <span className="text-white font-medium">{change.new}</span>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>
                    ) : null}
                </div>

                {/* Actions */}
                <div className="p-6 border-t border-white/10 bg-black/20">
                    <div className="flex gap-3">
                        <button
                            onClick={handleReject}
                            disabled={processing || loading}
                            className="flex-1 px-6 py-3 rounded-xl bg-red-500/20 text-red-400 border border-red-500/30 hover:bg-red-500/30 transition-all disabled:opacity-50 disabled:cursor-not-allowed font-semibold"
                        >
                            {processing ? 'Processing...' : 'Reject Change'}
                        </button>
                        <button
                            onClick={handleAccept}
                            disabled={processing || loading}
                            className="flex-1 px-6 py-3 rounded-xl bg-green-500/20 text-green-400 border border-green-500/30 hover:bg-green-500/30 transition-all disabled:opacity-50 disabled:cursor-not-allowed font-semibold flex items-center justify-center gap-2"
                        >
                            {processing ? (
                                'Processing...'
                            ) : (
                                <>
                                    <Check size={20} />
                                    Accept Change
                                </>
                            )}
                        </button>
                    </div>
                    <p className="text-xs text-gray-500 text-center mt-3">
                        Rejecting will cancel your flight and issue a credit to your account
                    </p>
                </div>
            </div>
        </div>
    );
};
