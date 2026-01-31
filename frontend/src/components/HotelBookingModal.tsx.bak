import React, { useState } from 'react';
import { X, Check, CheckCircle, Calendar, Users, Bed, MapPin } from 'lucide-react';
import axios from 'axios';
import API_URL from '../config/api';
import { PriceBreakdown } from './PriceBreakdown';
import { BusinessFooter } from './BusinessFooter';
import { HotelPolicyDisplay } from './HotelPolicyDisplay';

interface HotelBookingModalProps {
    isOpen: boolean;
    onClose: () => void;
    hotel: any;
}

export const HotelBookingModal: React.FC<HotelBookingModalProps> = ({
    isOpen,
    onClose,
    hotel,
}) => {
    const [isCreatingBooking, setIsCreatingBooking] = useState(false);
    const [bookingResult, setBookingResult] = useState<any>(null);
    const [paymentSuccess, setPaymentSuccess] = useState(false);
    const [acceptedTerms, setAcceptedTerms] = useState(false);

    if (!isOpen || !hotel) return null;

    // Extract hotel data
    const hotelName = hotel.name || 'Hotel';
    const hotelAddress = hotel.address || 'Address not available';
    const checkIn = hotel.checkIn || new Date().toISOString().split('T')[0];
    const checkOut = hotel.checkOut || new Date().toISOString().split('T')[0];
    const guests = hotel.guests || 2;
    const rooms = hotel.rooms || 1;

    // Calculate nights
    const nights = Math.ceil(
        (new Date(checkOut).getTime() - new Date(checkIn).getTime()) / (1000 * 60 * 60 * 24)
    );

    // Price breakdown
    const totalPrice = parseFloat(hotel.price || 0);
    const basePrice = totalPrice * 0.85; // Approximate base price
    const taxAmount = totalPrice * 0.10; // 10% tax
    const feeAmount = totalPrice * 0.05; // 5% fee
    const currency = hotel.currency || 'USD';

    // Policy information
    const hotelPolicy = {
        cancellationTimeline: hotel.cancellationPolicy || 'Free cancellation until 24 hours before check-in',
        hotelPolicies: [
            'Check-in requires a valid ID and credit card',
            'Smoking is not permitted',
            'Pets are not allowed',
            'Quiet hours: 10 PM - 7 AM',
        ],
        rateConditions: [
            'Non-refundable after cancellation deadline',
            'Rate includes breakfast',
            'Free WiFi included',
        ],
        checkInInstructions: 'Please proceed to the front desk with your booking confirmation and valid ID.',
        checkInTime: hotel.checkInTime || '3:00 PM',
        checkOutTime: hotel.checkOutTime || '11:00 AM',
    };

    const handleConfirmBooking = async () => {
        if (!acceptedTerms) {
            alert('Please accept the terms and conditions to proceed');
            return;
        }

        setIsCreatingBooking(true);
        try {
            const response = await axios.post(`${API_URL}/v1/booking/create`, {
                user_id: localStorage.getItem('user_id') || 'demo-user',
                offer_id: hotel.offer_id || hotel.id,
                provider: hotel.provider || 'liteapi',
                amount: totalPrice,
                currency: currency,
                hotel_data: {
                    name: hotelName,
                    address: hotelAddress,
                    check_in: checkIn,
                    check_out: checkOut,
                    guests: guests,
                    rooms: rooms,
                    nights: nights,
                },
            });

            setBookingResult(response.data.booking);
            setPaymentSuccess(true);
        } catch (error) {
            console.error('Error creating booking:', error);
            alert('Error creating booking. Please try again.');
        } finally {
            setIsCreatingBooking(false);
        }
    };

    // Success screen
    if (paymentSuccess && bookingResult) {
        return (
            <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
                <div className="bg-gray-900/95 backdrop-blur-xl border border-white/10 w-full max-w-2xl rounded-3xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200 max-h-[90vh] overflow-y-auto">
                    <div className="bg-gradient-to-r from-green-500 to-emerald-600 p-6 text-white text-center">
                        <CheckCircle size={64} className="mx-auto mb-4" />
                        <h2 className="text-2xl font-bold">Booking Confirmed!</h2>
                        <p className="opacity-90 text-sm mt-1">Your hotel reservation has been confirmed</p>
                        <p className="text-xs mt-2 opacity-75">
                            Confirmed on {new Date().toLocaleString()}
                        </p>
                    </div>

                    <div className="p-6 space-y-6">
                        {/* Confirmation Code */}
                        <div className="bg-white/5 p-4 rounded-xl border border-white/10">
                            <p className="text-sm text-gray-400">Booking Reference</p>
                            <p className="text-2xl font-bold text-white">{bookingResult.pnr || bookingResult.id}</p>
                        </div>

                        {/* Hotel Details */}
                        <div className="bg-white/5 p-4 rounded-xl border border-white/10 space-y-3">
                            <div>
                                <p className="text-sm text-gray-400">Hotel</p>
                                <p className="text-lg font-semibold text-white">{hotelName}</p>
                                <div className="text-sm text-gray-400 flex items-center gap-1 mt-1">
                                    <MapPin className="w-4 h-4" />
                                    {hotelAddress}
                                </div>
                            </div>

                            <div className="grid grid-cols-2 gap-4 pt-3 border-t border-gray-700">
                                <div>
                                    <p className="text-xs text-gray-400">Check-in</p>
                                    <p className="text-sm font-medium text-white">{new Date(checkIn).toLocaleDateString()}</p>
                                    <p className="text-xs text-gray-500">{hotelPolicy.checkInTime}</p>
                                </div>
                                <div>
                                    <p className="text-xs text-gray-400">Check-out</p>
                                    <p className="text-sm font-medium text-white">{new Date(checkOut).toLocaleDateString()}</p>
                                    <p className="text-xs text-gray-500">{hotelPolicy.checkOutTime}</p>
                                </div>
                            </div>

                            <div className="grid grid-cols-3 gap-4 pt-3 border-t border-gray-700">
                                <div>
                                    <p className="text-xs text-gray-400">Guests</p>
                                    <p className="text-sm font-medium text-white flex items-center gap-1">
                                        <Users className="w-4 h-4" />
                                        {guests}
                                    </p>
                                </div>
                                <div>
                                    <p className="text-xs text-gray-400">Rooms</p>
                                    <p className="text-sm font-medium text-white flex items-center gap-1">
                                        <Bed className="w-4 h-4" />
                                        {rooms}
                                    </p>
                                </div>
                                <div>
                                    <p className="text-xs text-gray-400">Nights</p>
                                    <p className="text-sm font-medium text-white flex items-center gap-1">
                                        <Calendar className="w-4 h-4" />
                                        {nights}
                                    </p>
                                </div>
                            </div>
                        </div>

                        {/* Price Breakdown */}
                        <PriceBreakdown
                            basePrice={basePrice}
                            taxAmount={taxAmount}
                            feeAmount={feeAmount}
                            total={totalPrice}
                            currency={currency}
                        />

                        {/* Hotel Policies */}
                        <HotelPolicyDisplay policy={hotelPolicy} />

                        {/* Business Footer */}
                        <BusinessFooter variant="compact" />

                        <button
                            onClick={onClose}
                            className="w-full py-3 bg-primary hover:bg-primary/90 text-white rounded-xl font-bold transition-all"
                        >
                            Done
                        </button>
                    </div>
                </div>
            </div>
        );
    }

    // Booking confirmation screen
    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
            <div className="bg-gray-900/95 backdrop-blur-xl border border-white/10 w-full max-w-2xl rounded-3xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200 max-h-[90vh] overflow-y-auto">
                {/* Header */}
                <div className="bg-gradient-to-r from-primary to-accent p-6 text-white relative">
                    <button
                        onClick={onClose}
                        className="absolute top-4 right-4 p-2 hover:bg-white/20 rounded-full transition-colors"
                    >
                        <X size={20} />
                    </button>
                    <h2 className="text-2xl font-bold">Confirm Hotel Booking</h2>
                    <p className="opacity-90 text-sm mt-1">Review your reservation details</p>
                </div>

                <div className="p-6 space-y-6">
                    {/* Hotel Summary */}
                    <div className="bg-secondary/30 rounded-2xl border border-white/5 p-4 space-y-3">
                        <div>
                            <h3 className="text-xl font-bold text-white">{hotelName}</h3>
                            <div className="text-sm text-gray-400 flex items-center gap-1 mt-1">
                                <MapPin className="w-4 h-4" />
                                {hotelAddress}
                            </div>
                        </div>

                        <div className="grid grid-cols-2 gap-4 pt-3 border-t border-gray-700">
                            <div>
                                <p className="text-xs text-gray-400">Check-in</p>
                                <p className="text-sm font-medium text-white">{new Date(checkIn).toLocaleDateString()}</p>
                                <p className="text-xs text-gray-500">{hotelPolicy.checkInTime}</p>
                            </div>
                            <div>
                                <p className="text-xs text-gray-400">Check-out</p>
                                <p className="text-sm font-medium text-white">{new Date(checkOut).toLocaleDateString()}</p>
                                <p className="text-xs text-gray-500">{hotelPolicy.checkOutTime}</p>
                            </div>
                        </div>

                        <div className="grid grid-cols-3 gap-4 pt-3 border-t border-gray-700">
                            <div>
                                <p className="text-xs text-gray-400">Guests</p>
                                <p className="text-sm font-medium text-white flex items-center gap-1">
                                    <Users className="w-4 h-4" />
                                    {guests}
                                </p>
                            </div>
                            <div>
                                <p className="text-xs text-gray-400">Rooms</p>
                                <p className="text-sm font-medium text-white flex items-center gap-1">
                                    <Bed className="w-4 h-4" />
                                    {rooms}
                                </p>
                            </div>
                            <div>
                                <p className="text-xs text-gray-400">Nights</p>
                                <p className="text-sm font-medium text-white flex items-center gap-1">
                                    <Calendar className="w-4 h-4" />
                                    {nights}
                                </p>
                            </div>
                        </div>
                    </div>

                    {/* Price Breakdown */}
                    <PriceBreakdown
                        basePrice={basePrice}
                        taxAmount={taxAmount}
                        feeAmount={feeAmount}
                        total={totalPrice}
                        currency={currency}
                    />

                    {/* Hotel Policies */}
                    <HotelPolicyDisplay policy={hotelPolicy} compact />

                    {/* Terms and Conditions */}
                    <div className="bg-gray-800/30 rounded-lg p-4">
                        <label className="flex items-start gap-3 cursor-pointer">
                            <input
                                type="checkbox"
                                checked={acceptedTerms}
                                onChange={(e) => setAcceptedTerms(e.target.checked)}
                                className="w-5 h-5 mt-0.5 rounded border-gray-600 bg-gray-800 text-primary focus:ring-primary"
                            />
                            <span className="text-sm text-gray-300">
                                I agree to the{' '}
                                <a href="/terms" className="text-blue-400 hover:text-blue-300 underline">
                                    Terms & Conditions
                                </a>
                                ,{' '}
                                <a href="/privacy" className="text-blue-400 hover:text-blue-300 underline">
                                    Privacy Policy
                                </a>
                                , and{' '}
                                <a
                                    href="https://www.booking.com/content/terms.html"
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-blue-400 hover:text-blue-300 underline"
                                >
                                    Booking.com Terms
                                </a>
                            </span>
                        </label>
                    </div>

                    {/* Business Footer */}
                    <BusinessFooter variant="compact" />

                    {/* Confirm Button */}
                    <button
                        onClick={handleConfirmBooking}
                        disabled={isCreatingBooking || !acceptedTerms}
                        className="w-full py-4 bg-primary hover:bg-primary/90 text-white rounded-xl font-bold text-lg shadow-lg shadow-primary/25 transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                    >
                        {isCreatingBooking ? (
                            'Creating Booking...'
                        ) : (
                            <>
                                <Check size={20} />
                                Confirm Booking
                            </>
                        )}
                    </button>
                </div>
            </div>
        </div>
    );
};

export default HotelBookingModal;
