import React, { useState, useEffect } from 'react';
import { X, Check, Armchair, Wallet, CheckCircle, Clock, AlertCircle } from 'lucide-react';
import { SeatMap } from './SeatMap';
import axios from 'axios';
import API_URL from '../config/api';

interface BookingModalProps {
    isOpen: boolean;
    onClose: () => void;
    onConfirm: (seatServiceId?: string, extraCost?: number, seatDesignator?: string) => void;
    flight: any;
    preferences: {
        seat: string;
        baggage: string;
    };
}

const BookingModalContent: React.FC<BookingModalProps> = ({ isOpen, onClose, flight, preferences }) => {
    const [showSeatMap, setShowSeatMap] = useState(false);
    const [selectedSeat, setSelectedSeat] = useState<any>(null);
    const [bookingResult, setBookingResult] = useState<any>(null);
    const [isCreatingIntent, setIsCreatingIntent] = useState(false);
    const [paymentSuccess, setPaymentSuccess] = useState(false);
    const [numPassengers, setNumPassengers] = useState(1);

    // Airline Credits state
    const [availableCredits, setAvailableCredits] = useState<any[]>([]);
    const [selectedCredit, setSelectedCredit] = useState<any>(null);

    // Hold order state
    const [holdAvailable, setHoldAvailable] = useState<{available: boolean; hold_hours?: number; message?: string} | null>(null);
    const [isCreatingHold, setIsCreatingHold] = useState(false);
    const [holdResult, setHoldResult] = useState<any>(null);

    // Fetch available credits and check hold availability when modal opens
    useEffect(() => {
        if (isOpen && flight) {
            fetchAvailableCredits();
            checkHoldAvailability();
        }
    }, [isOpen, flight]);

    const fetchAvailableCredits = async () => {
        try {
            const userId = localStorage.getItem('user_id') || 'demo-user';
            const airlineCode = flight.segments[0]?.carrier_code;

            if (airlineCode) {
                const response = await axios.get(
                    `${API_URL}/v1/credits/available/${userId}/${airlineCode}`
                );
                setAvailableCredits(response.data.credits || []);
            }
        } catch (error) {
            console.error('Error fetching credits:', error);
        }
    };

    const checkHoldAvailability = async () => {
        try {
            const response = await axios.get(`${API_URL}/api/hold-orders/check/${flight.offer_id}`);
            setHoldAvailable(response.data);
        } catch (error) {
            console.error('Error checking hold availability:', error);
            setHoldAvailable({ available: false });
        }
    };

    const handleCreateHold = async () => {
        setIsCreatingHold(true);
        try {
            // Get user profile for passenger data
            const userId = localStorage.getItem('user_id') || 'demo-user';
            let profileRes;
            try {
                profileRes = await axios.get(`${API_URL}/v1/profile/${userId}`);
            } catch {
                profileRes = { data: null };
            }

            const profile = profileRes.data || {};

            const passengers = [{
                type: 'adult',
                given_name: profile.legal_first_name || 'John',
                family_name: profile.legal_last_name || 'Doe',
                gender: 'm',
                born_on: profile.dob || '1990-01-01',
                email: profile.email || 'user@example.com',
                phone_number: profile.phone_number || '+1234567890'
            }];

            const response = await axios.post(`${API_URL}/api/hold-orders/create`, {
                offer_id: flight.offer_id,
                passengers: passengers,
                metadata: { user_id: userId }
            });

            if (response.data.success) {
                setHoldResult(response.data);
            } else {
                alert(response.data.error || 'Error al crear reserva');
            }
        } catch (error: any) {
            console.error('Error creating hold:', error);
            alert(error.response?.data?.detail || 'Error al crear reserva');
        } finally {
            setIsCreatingHold(false);
        }
    };

    if (!flight || !flight.segments || flight.segments.length === 0) {
        return null;
    }

    const firstSegment = flight.segments[0];
    const lastSegment = flight.segments[flight.segments.length - 1];

    // Calculate pricing
    const basePrice = parseFloat(flight.price);
    const seatCost = selectedSeat ? parseFloat(selectedSeat.price) : 0;
    const creditDiscount = selectedCredit ? parseFloat(selectedCredit.credit_amount) : 0;
    const subtotal = (basePrice * numPassengers) + seatCost;
    const totalPrice = Math.max(0, subtotal - creditDiscount).toFixed(2);

    const handleProceedToBooking = async () => {
        setIsCreatingIntent(true);
        try {
            const response = await axios.post(`${API_URL}/v1/booking/create`, {
                user_id: localStorage.getItem('user_id') || 'demo-user',
                offer_id: flight.offer_id,
                provider: flight.provider,
                amount: parseFloat(totalPrice),
                currency: flight.currency || 'USD',
                seat_service_id: selectedSeat?.serviceId,
                credit_id: selectedCredit?.id,
                num_passengers: numPassengers
            });

            setBookingResult(response.data.booking);
            setPaymentSuccess(true);
        } catch (error) {
            console.error('Error creating booking:', error);
            alert('Error creating booking. Please try again.');
        } finally {
            setIsCreatingIntent(false);
        }
    };

    // Hold success screen
    if (holdResult) {
        return (
            <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
                <div className="bg-gray-900/95 backdrop-blur-xl border border-white/10 w-full max-w-md max-w-[90vw] rounded-3xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200">
                    <div className="bg-gradient-to-r from-amber-500 to-orange-600 p-6 text-white text-center">
                        <Clock size={64} className="mx-auto mb-4" />
                        <h2 className="text-2xl font-bold">Reserva Creada</h2>
                        <p className="opacity-90 text-sm mt-1">Pendiente de pago</p>
                    </div>

                    <div className="p-6 space-y-4">
                        <div className="bg-white/5 p-4 rounded-xl border border-white/10">
                            <p className="text-sm text-gray-400">Código de Reserva</p>
                            <p className="text-2xl font-bold text-white">{holdResult.booking_reference}</p>
                        </div>

                        <div className="bg-white/5 p-4 rounded-xl border border-white/10">
                            <p className="text-sm text-gray-400">Total a Pagar</p>
                            <p className="text-xl font-semibold text-green-400">
                                ${holdResult.total_amount} {holdResult.total_currency}
                            </p>
                        </div>

                        <div className="bg-amber-500/20 p-4 rounded-xl border border-amber-500/30">
                            <div className="flex items-start gap-2">
                                <AlertCircle size={18} className="text-amber-400 flex-shrink-0 mt-0.5" />
                                <div>
                                    <p className="text-sm text-amber-200 font-medium">Pagar antes de:</p>
                                    <p className="text-amber-100">
                                        {holdResult.payment_required_by ?
                                            new Date(holdResult.payment_required_by).toLocaleString('es-MX') :
                                            '24 horas'}
                                    </p>
                                </div>
                            </div>
                        </div>

                        <button
                            onClick={() => {
                                setHoldResult(null);
                                onClose();
                            }}
                            className="w-full py-3 bg-primary hover:bg-primary/90 text-white rounded-xl font-bold transition-all"
                        >
                            Entendido
                        </button>
                    </div>
                </div>
            </div>
        );
    }

    // Success screen
    if (paymentSuccess && bookingResult) {
        return (
            <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
                <div className="bg-gray-900/95 backdrop-blur-xl border border-white/10 w-full max-w-md max-w-[90vw] rounded-3xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200">
                    <div className="bg-gradient-to-r from-green-500 to-emerald-600 p-6 text-white text-center">
                        <CheckCircle size={64} className="mx-auto mb-4" />
                        <h2 className="text-2xl font-bold">Booking Confirmed!</h2>
                        <p className="opacity-90 text-sm mt-1">Your flight has been booked successfully</p>
                    </div>

                    <div className="p-6 space-y-4">
                        <div className="bg-white/5 p-4 rounded-xl border border-white/10">
                            <p className="text-sm text-gray-400">Confirmation Code</p>
                            <p className="text-2xl font-bold text-white">{bookingResult.pnr}</p>
                        </div>

                        <div className="bg-white/5 p-4 rounded-xl border border-white/10">
                            <p className="text-sm text-gray-400">Flight</p>
                            <p className="text-lg font-semibold">{firstSegment.departure_iata} → {lastSegment.arrival_iata}</p>
                        </div>

                        <button
                            onClick={() => {
                                setPaymentSuccess(false);
                                setBookingResult(null);
                                onClose();
                            }}
                            className="w-full py-3 bg-primary hover:bg-primary/90 text-white rounded-xl font-bold transition-all"
                        >
                            Done
                        </button>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="fixed inset-0 z-50 flex items-start sm:items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200 overflow-y-auto">
            <div className={`bg-gray-900/95 backdrop-blur-xl border border-white/10 w-full ${showSeatMap ? 'max-w-4xl' : 'max-w-md'} max-w-[90vw] rounded-3xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200 transition-all my-8`}>
                <div className="bg-gradient-to-r from-primary to-accent p-6 text-white relative">
                    <button onClick={onClose} className="absolute top-4 right-4 p-2 hover:bg-white/20 rounded-full transition-colors">
                        <X size={20} />
                    </button>
                    <h2 className="text-2xl font-bold">Confirm Booking</h2>
                    <p className="opacity-90 text-sm mt-1">Review your flight details</p>
                </div>

                <div className="flex flex-col md:flex-row">
                    <div className="p-6 space-y-6 flex-1">
                        {/* Passenger Count Selector */}
                        <div className="p-4 bg-secondary/20 rounded-2xl border border-white/5">
                            <label className="text-sm text-gray-400 mb-2 block">Number of Passengers</label>
                            <div className="flex items-center justify-between gap-4">
                                <button
                                    onClick={() => setNumPassengers(Math.max(1, numPassengers - 1))}
                                    className="w-10 h-10 rounded-xl bg-white/10 hover:bg-white/20 transition-colors flex items-center justify-center font-bold"
                                    disabled={numPassengers <= 1}
                                >
                                    −
                                </button>
                                <span className="text-2xl font-bold">{numPassengers}</span>
                                <button
                                    onClick={() => setNumPassengers(Math.min(9, numPassengers + 1))}
                                    className="w-10 h-10 rounded-xl bg-white/10 hover:bg-white/20 transition-colors flex items-center justify-center font-bold"
                                    disabled={numPassengers >= 9}
                                >
                                    +
                                </button>
                            </div>
                        </div>

                        {/* Flight Summary */}
                        <div className="flex items-center justify-between p-4 bg-secondary/30 rounded-2xl border border-white/5">
                            <div className="flex items-center gap-3">
                                <div className="w-10 h-10 rounded-full bg-white flex items-center justify-center overflow-hidden">
                                    <img
                                        src={`https://pics.avs.io/200/200/${firstSegment.carrier_code}.png`}
                                        alt={firstSegment.carrier_code}
                                        className="w-full h-full object-contain"
                                        onError={(e) => {
                                            const target = e.target as HTMLImageElement;
                                            target.style.display = 'none';
                                        }}
                                    />
                                </div>
                                <div>
                                    <p className="font-bold text-lg">{firstSegment.departure_iata} → {lastSegment.arrival_iata}</p>
                                    <p className="text-xs text-gray-400">{firstSegment.carrier_code} {firstSegment.flight_number}</p>
                                </div>
                            </div>
                            <div className="text-right">
                                <p className="text-2xl font-bold text-green-400">${totalPrice}</p>
                                {numPassengers > 1 && <p className="text-xs text-blue-400">${basePrice} × {numPassengers} passengers</p>}
                                {seatCost > 0 && <p className="text-xs text-amber-400">(+${seatCost} seat)</p>}
                                {selectedCredit && <p className="text-xs text-green-400">(-${creditDiscount.toFixed(2)} credit)</p>}
                                <p className="text-xs text-gray-400">Total</p>
                            </div>
                        </div>

                        {/* Seat Selection Button */}
                        {!showSeatMap && (
                            <button
                                onClick={() => setShowSeatMap(true)}
                                className="w-full py-3 bg-amber-600/20 hover:bg-amber-600/30 border border-amber-500/30 text-amber-200 rounded-xl font-medium transition-all flex items-center justify-center gap-2"
                            >
                                <Armchair size={18} />
                                {selectedSeat ? `Change Seat (${selectedSeat.designator})` : 'Select Seat'}
                            </button>
                        )}

                        {/* Airline Credits Selector */}
                        {availableCredits.length > 0 && (
                            <div className="p-4 bg-green-900/20 rounded-2xl border border-green-500/30">
                                <label className="text-sm text-green-300 mb-2 block flex items-center gap-2">
                                    <Wallet size={16} />
                                    Available Credits
                                </label>
                                <select
                                    value={selectedCredit?.id || ''}
                                    onChange={(e) => {
                                        const credit = availableCredits.find(c => c.id === e.target.value);
                                        setSelectedCredit(credit || null);
                                    }}
                                    className="w-full bg-white/10 border border-white/20 rounded-xl px-4 py-2 text-sm"
                                >
                                    <option value="">No credit applied</option>
                                    {availableCredits.map(credit => (
                                        <option key={credit.id} value={credit.id}>
                                            ${credit.credit_amount} ({credit.airline_code})
                                        </option>
                                    ))}
                                </select>
                            </div>
                        )}

                        <button
                            onClick={handleProceedToBooking}
                            disabled={isCreatingIntent}
                            className="w-full py-4 bg-gradient-to-r from-primary to-accent text-white rounded-2xl font-bold text-lg hover:opacity-90 transition-all disabled:opacity-50 flex items-center justify-center gap-2"
                        >
                            {isCreatingIntent ? (
                                'Creating Booking...'
                            ) : (
                                <>
                                    <Check size={20} />
                                    Confirm Booking
                                </>
                            )}
                        </button>

                        {/* Hold Order Button */}
                        {holdAvailable?.available && (
                            <button
                                onClick={handleCreateHold}
                                disabled={isCreatingHold}
                                className="w-full py-3 bg-amber-600/20 hover:bg-amber-600/30 border border-amber-500/30 text-amber-200 rounded-xl font-medium transition-all disabled:opacity-50 flex items-center justify-center gap-2"
                            >
                                {isCreatingHold ? (
                                    'Reservando...'
                                ) : (
                                    <>
                                        <Clock size={18} />
                                        Reservar sin Pagar ({holdAvailable.hold_hours}h)
                                    </>
                                )}
                            </button>
                        )}
                    </div>

                    {showSeatMap && (
                        <div className="p-6 bg-black/20 border-l border-white/5 w-full md:w-[400px] flex flex-col">
                            <h3 className="text-lg font-bold mb-4 flex items-center gap-2">
                                <Armchair size={20} /> Select Your Seat
                            </h3>
                            <div className="flex-1 overflow-y-auto min-h-[400px] bg-white/5 rounded-2xl">
                                <SeatMap
                                    offerId={flight.offer_id}
                                    onSelect={setSelectedSeat}
                                    seatPreference={preferences.seat}
                                    positionPreference="MIDDLE"
                                />
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export const BookingModal: React.FC<BookingModalProps> = (props) => {
    return <BookingModalContent {...props} />;
};
