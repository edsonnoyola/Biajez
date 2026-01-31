import React from 'react';
import { DollarSign } from 'lucide-react';

interface PriceBreakdownProps {
    basePrice: number;
    taxAmount: number;
    feeAmount: number;
    dueAtProperty?: number;
    total: number;
    currency: string;
    compact?: boolean;
}

export const PriceBreakdown: React.FC<PriceBreakdownProps> = ({
    basePrice,
    taxAmount,
    feeAmount,
    dueAtProperty,
    total,
    currency,
    compact = false,
}) => {
    const formatPrice = (amount: number) => {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: currency,
        }).format(amount);
    };

    if (compact) {
        return (
            <div className="price-breakdown-compact">
                <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-400">Total</span>
                    <span className="text-white font-semibold">{formatPrice(total)}</span>
                </div>
                <button
                    className="text-xs text-blue-400 hover:text-blue-300 mt-1"
                    onClick={(e) => {
                        e.stopPropagation();
                        const details = e.currentTarget.nextElementSibling;
                        if (details) {
                            details.classList.toggle('hidden');
                        }
                    }}
                >
                    View price breakdown
                </button>
                <div className="hidden mt-2 p-3 bg-gray-800/50 rounded-lg text-xs space-y-1">
                    <div className="flex justify-between">
                        <span className="text-gray-400">Base price</span>
                        <span className="text-gray-300">{formatPrice(basePrice)}</span>
                    </div>
                    <div className="flex justify-between">
                        <span className="text-gray-400">Taxes</span>
                        <span className="text-gray-300">{formatPrice(taxAmount)}</span>
                    </div>
                    <div className="flex justify-between">
                        <span className="text-gray-400">Fees</span>
                        <span className="text-gray-300">{formatPrice(feeAmount)}</span>
                    </div>
                    {dueAtProperty && dueAtProperty > 0 && (
                        <div className="flex justify-between text-yellow-400">
                            <span>Due at property</span>
                            <span>{formatPrice(dueAtProperty)}</span>
                        </div>
                    )}
                    <div className="flex justify-between border-t border-gray-700 pt-1 mt-1">
                        <span className="text-white font-semibold">Total</span>
                        <span className="text-white font-semibold">{formatPrice(total)}</span>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="price-breakdown">
            <div className="flex items-center gap-2 mb-3">
                <DollarSign className="w-5 h-5 text-green-400" />
                <h3 className="text-lg font-semibold text-white">Price Breakdown</h3>
            </div>

            <div className="space-y-2 bg-gray-800/30 rounded-lg p-4">
                <div className="flex justify-between items-center">
                    <span className="text-gray-400">Base price</span>
                    <span className="text-gray-200">{formatPrice(basePrice)}</span>
                </div>

                <div className="flex justify-between items-center">
                    <span className="text-gray-400">Taxes</span>
                    <span className="text-gray-200">{formatPrice(taxAmount)}</span>
                </div>

                <div className="flex justify-between items-center">
                    <span className="text-gray-400">Service fees</span>
                    <span className="text-gray-200">{formatPrice(feeAmount)}</span>
                </div>

                {dueAtProperty && dueAtProperty > 0 && (
                    <>
                        <div className="border-t border-gray-700 my-2"></div>
                        <div className="flex justify-between items-center text-yellow-400">
                            <span className="font-medium">Due at property</span>
                            <span className="font-semibold">{formatPrice(dueAtProperty)}</span>
                        </div>
                        <p className="text-xs text-gray-500 mt-1">
                            This amount will be collected by the property upon arrival
                        </p>
                    </>
                )}

                <div className="border-t border-gray-700 my-2"></div>

                <div className="flex justify-between items-center">
                    <span className="text-white font-bold text-lg">Total</span>
                    <span className="text-green-400 font-bold text-lg">{formatPrice(total)}</span>
                </div>
            </div>
        </div>
    );
};

export default PriceBreakdown;
