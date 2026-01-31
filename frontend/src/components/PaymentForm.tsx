import React, { useState } from 'react';
import { PaymentElement, useStripe, useElements } from '@stripe/react-stripe-js';
import { Loader2, CreditCard, Lock } from 'lucide-react';

interface PaymentFormProps {
    amount: number;
    currency: string;
    onSuccess: (paymentIntentId: string) => void;
    onError: (error: string) => void;
}

export const PaymentForm: React.FC<PaymentFormProps> = ({ amount, currency, onSuccess, onError }) => {
    const stripe = useStripe();
    const elements = useElements();
    const [isProcessing, setIsProcessing] = useState(false);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();

        if (!stripe || !elements) {
            return;
        }

        setIsProcessing(true);
        setErrorMessage(null);

        try {
            // Confirm the payment
            const { error, paymentIntent } = await stripe.confirmPayment({
                elements,
                confirmParams: {
                    return_url: window.location.origin + '/payment-success',
                },
                redirect: 'if_required', // Only redirect if 3D Secure is needed
            });

            if (error) {
                setErrorMessage(error.message || 'Payment failed');
                onError(error.message || 'Payment failed');
                setIsProcessing(false);
            } else if (paymentIntent && paymentIntent.status === 'succeeded') {
                onSuccess(paymentIntent.id);
            }
        } catch (err: any) {
            setErrorMessage(err.message || 'An unexpected error occurred');
            onError(err.message || 'An unexpected error occurred');
            setIsProcessing(false);
        }
    };

    return (
        <form onSubmit={handleSubmit} className="space-y-6">
            {/* Payment Amount Display */}
            <div className="bg-gradient-to-r from-primary/20 to-accent/20 p-4 rounded-xl border border-white/10">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <CreditCard className="text-primary" size={20} />
                        <span className="text-sm text-gray-400">Total Amount</span>
                    </div>
                    <div className="text-2xl font-bold text-white">
                        ${amount.toFixed(2)} {currency}
                    </div>
                </div>
            </div>

            {/* Stripe Payment Element */}
            <div className="bg-white/5 p-4 rounded-xl border border-white/10">
                <PaymentElement
                    options={{
                        layout: 'tabs',
                        defaultValues: {
                            billingDetails: {
                                address: {
                                    country: 'US',
                                },
                            },
                        },
                    }}
                />
            </div>

            {/* Error Message */}
            {errorMessage && (
                <div className="bg-red-500/10 border border-red-500/50 rounded-xl p-4 animate-in fade-in duration-200">
                    <p className="text-red-400 text-sm">{errorMessage}</p>
                </div>
            )}

            {/* Security Badge */}
            <div className="flex items-center justify-center gap-2 text-xs text-gray-400">
                <Lock size={12} />
                <span>Secured by Stripe • PCI DSS Compliant</span>
            </div>

            {/* Submit Button */}
            <button
                type="submit"
                disabled={!stripe || isProcessing}
                className="w-full py-4 bg-gradient-to-r from-primary to-accent hover:opacity-90 text-white rounded-xl font-bold text-lg shadow-lg shadow-primary/25 transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
                {isProcessing ? (
                    <>
                        <Loader2 className="animate-spin" size={20} />
                        Processing Payment...
                    </>
                ) : (
                    <>
                        <Lock size={18} />
                        Pay ${amount.toFixed(2)}
                    </>
                )}
            </button>
        </form>
    );
};
