import React, { useState, useEffect } from 'react';
import { X, Wallet, Calendar, AlertCircle, CheckCircle2 } from 'lucide-react';
import axios from 'axios';

interface Credit {
    id: string;
    airline_iata_code: string;
    credit_amount: number;
    credit_currency: string;
    credit_name: string;
    credit_code: string | null;
    expires_at: string | null;
    spent_at: string | null;
    is_valid: boolean;
    is_expired: boolean;
    created_at: string;
}

interface CreditsModalProps {
    isOpen: boolean;
    onClose: () => void;
    userId: string;
}

export const CreditsModal: React.FC<CreditsModalProps> = ({ isOpen, onClose, userId }) => {
    const [credits, setCredits] = useState<Credit[]>([]);
    const [loading, setLoading] = useState(false);
    const [showSpent, setShowSpent] = useState(false);

    useEffect(() => {
        if (isOpen) {
            fetchCredits();
        }
    }, [isOpen, showSpent]);

    const fetchCredits = async () => {
        setLoading(true);
        try {
            const response = await axios.get(
                `http://localhost:8000/v1/credits/${userId}?include_spent=${showSpent}`
            );
            setCredits(response.data.credits || []);
        } catch (error) {
            console.error('Error fetching credits:', error);
        } finally {
            setLoading(false);
        }
    };

    const formatDate = (dateString: string | null) => {
        if (!dateString) return 'No expiration';
        try {
            return new Date(dateString).toLocaleDateString('en-US', {
                year: 'numeric',
                month: 'short',
                day: 'numeric'
            });
        } catch {
            return 'Invalid date';
        }
    };

    const getTotalBalance = () => {
        const balances: { [key: string]: number } = {};
        credits.forEach(credit => {
            if (credit.is_valid) {
                const curr = credit.credit_currency;
                balances[curr] = (balances[curr] || 0) + credit.credit_amount;
            }
        });
        return balances;
    };

    const balances = getTotalBalance();
    const availableCredits = credits.filter(c => c.is_valid);
    const usedCredits = credits.filter(c => c.spent_at);
    const expiredCredits = credits.filter(c => c.is_expired && !c.spent_at);

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
            <div className="bg-gray-900/95 backdrop-blur-xl border border-white/10 w-full max-w-3xl rounded-3xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200 flex flex-col max-h-[90vh]">

                {/* Header */}
                <div className="bg-gradient-to-r from-green-900 to-gray-900 p-6 text-white relative flex items-center justify-between border-b border-white/5">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-green-500/20 flex items-center justify-center text-green-400">
                            <Wallet size={20} />
                        </div>
                        <div>
                            <h2 className="text-xl font-bold">My Flight Credits</h2>
                            <p className="text-sm text-gray-400">
                                {availableCredits.length} available credit{availableCredits.length !== 1 ? 's' : ''}
                            </p>
                        </div>
                    </div>
                    <button onClick={onClose} className="p-2 hover:bg-white/10 rounded-full transition-colors">
                        <X size={20} />
                    </button>
                </div>

                {/* Total Balance */}
                {Object.keys(balances).length > 0 && (
                    <div className="p-6 bg-gradient-to-r from-green-500/10 to-blue-500/10 border-b border-white/5">
                        <p className="text-sm text-gray-400 mb-2">Total Available Balance</p>
                        <div className="flex gap-4">
                            {Object.entries(balances).map(([currency, amount]) => (
                                <div key={currency} className="flex items-baseline gap-2">
                                    <span className="text-3xl font-bold text-green-400">
                                        {currency} ${amount.toFixed(2)}
                                    </span>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* Filter Toggle */}
                <div className="p-4 border-b border-white/5">
                    <label className="flex items-center gap-2 cursor-pointer">
                        <input
                            type="checkbox"
                            checked={showSpent}
                            onChange={(e) => setShowSpent(e.target.checked)}
                            className="w-4 h-4 rounded border-gray-600 bg-gray-800 text-blue-500 focus:ring-blue-500"
                        />
                        <span className="text-sm text-gray-300">Show used and expired credits</span>
                    </label>
                </div>

                {/* Credits List */}
                <div className="p-6 overflow-y-auto custom-scrollbar flex-1">
                    {loading ? (
                        <div className="text-center py-8">
                            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto"></div>
                            <p className="text-gray-400 mt-2">Loading credits...</p>
                        </div>
                    ) : credits.length === 0 ? (
                        <div className="text-center py-12">
                            <Wallet className="mx-auto text-gray-600 mb-4" size={48} />
                            <p className="text-gray-400">No flight credits yet</p>
                            <p className="text-sm text-gray-500 mt-2">
                                Credits will appear here when you cancel or change flights
                            </p>
                        </div>
                    ) : (
                        <div className="space-y-4">
                            {/* Available Credits */}
                            {availableCredits.length > 0 && (
                                <div>
                                    <h3 className="text-sm font-semibold text-gray-400 mb-3 uppercase tracking-wide">
                                        Available Credits
                                    </h3>
                                    <div className="space-y-3">
                                        {availableCredits.map((credit) => (
                                            <div
                                                key={credit.id}
                                                className="bg-white/5 border border-green-500/30 rounded-xl p-4 hover:bg-white/10 transition-colors"
                                            >
                                                <div className="flex items-start justify-between">
                                                    <div className="flex-1">
                                                        <div className="flex items-center gap-3 mb-2">
                                                            <span className="px-3 py-1 bg-blue-500/20 text-blue-400 rounded-full text-sm font-mono font-semibold">
                                                                {credit.airline_iata_code}
                                                            </span>
                                                            <span className="text-2xl font-bold text-green-400">
                                                                {credit.credit_currency} ${credit.credit_amount.toFixed(2)}
                                                            </span>
                                                        </div>
                                                        <p className="text-gray-300 text-sm mb-2">
                                                            {credit.credit_name || 'Flight Credit'}
                                                        </p>
                                                        {credit.credit_code && (
                                                            <p className="text-xs text-gray-500 font-mono">
                                                                Code: {credit.credit_code}
                                                            </p>
                                                        )}
                                                    </div>
                                                    <div className="text-right">
                                                        <div className="flex items-center gap-1 text-green-400 mb-1">
                                                            <CheckCircle2 size={16} />
                                                            <span className="text-xs font-semibold">ACTIVE</span>
                                                        </div>
                                                        <div className="flex items-center gap-1 text-gray-400 text-xs">
                                                            <Calendar size={12} />
                                                            <span>Expires: {formatDate(credit.expires_at)}</span>
                                                        </div>
                                                    </div>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* Expired Credits */}
                            {showSpent && expiredCredits.length > 0 && (
                                <div className="mt-6">
                                    <h3 className="text-sm font-semibold text-gray-400 mb-3 uppercase tracking-wide">
                                        Expired Credits
                                    </h3>
                                    <div className="space-y-3">
                                        {expiredCredits.map((credit) => (
                                            <div
                                                key={credit.id}
                                                className="bg-white/5 border border-red-500/20 rounded-xl p-4 opacity-60"
                                            >
                                                <div className="flex items-start justify-between">
                                                    <div className="flex-1">
                                                        <div className="flex items-center gap-3 mb-2">
                                                            <span className="px-3 py-1 bg-gray-500/20 text-gray-400 rounded-full text-sm font-mono">
                                                                {credit.airline_iata_code}
                                                            </span>
                                                            <span className="text-xl font-bold text-gray-500 line-through">
                                                                {credit.credit_currency} ${credit.credit_amount.toFixed(2)}
                                                            </span>
                                                        </div>
                                                    </div>
                                                    <span className="text-xs text-red-400 font-semibold">EXPIRED</span>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* Used Credits */}
                            {showSpent && usedCredits.length > 0 && (
                                <div className="mt-6">
                                    <h3 className="text-sm font-semibold text-gray-400 mb-3 uppercase tracking-wide">
                                        Used Credits
                                    </h3>
                                    <div className="space-y-3">
                                        {usedCredits.map((credit) => (
                                            <div
                                                key={credit.id}
                                                className="bg-white/5 border border-gray-500/20 rounded-xl p-4 opacity-60"
                                            >
                                                <div className="flex items-start justify-between">
                                                    <div className="flex-1">
                                                        <div className="flex items-center gap-3 mb-2">
                                                            <span className="px-3 py-1 bg-gray-500/20 text-gray-400 rounded-full text-sm font-mono">
                                                                {credit.airline_iata_code}
                                                            </span>
                                                            <span className="text-xl font-bold text-gray-500">
                                                                {credit.credit_currency} ${credit.credit_amount.toFixed(2)}
                                                            </span>
                                                        </div>
                                                        <p className="text-xs text-gray-500">
                                                            Used on {formatDate(credit.spent_at)}
                                                        </p>
                                                    </div>
                                                    <span className="text-xs text-gray-400 font-semibold">USED</span>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>
                    )}
                </div>

                {/* Footer */}
                <div className="p-4 border-t border-white/5 bg-gray-900/50">
                    <div className="flex items-start gap-2 text-xs text-gray-400">
                        <AlertCircle size={14} className="flex-shrink-0 mt-0.5" />
                        <p>
                            Credits can only be used for flights with the same airline. They cannot be transferred or refunded for cash.
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
};
