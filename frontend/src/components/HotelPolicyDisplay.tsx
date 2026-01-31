import React, { useState } from 'react';
import { Info, Calendar, Clock, Key, AlertCircle, ChevronDown, ChevronUp } from 'lucide-react';

interface HotelPolicy {
    cancellationTimeline?: string;
    hotelPolicies?: string[];
    rateConditions?: string[];
    checkInInstructions?: string;
    keyCollectionInfo?: string;
    checkInTime?: string;
    checkOutTime?: string;
}

interface HotelPolicyDisplayProps {
    policy: HotelPolicy;
    compact?: boolean;
}

export const HotelPolicyDisplay: React.FC<HotelPolicyDisplayProps> = ({
    policy,
    compact = false,
}) => {
    const [isExpanded, setIsExpanded] = useState(!compact);

    const hasContent =
        policy.cancellationTimeline ||
        (policy.hotelPolicies && policy.hotelPolicies.length > 0) ||
        (policy.rateConditions && policy.rateConditions.length > 0) ||
        policy.checkInInstructions ||
        policy.keyCollectionInfo;

    if (!hasContent) {
        return null;
    }

    if (compact) {
        return (
            <div className="hotel-policy-compact">
                <button
                    onClick={() => setIsExpanded(!isExpanded)}
                    className="w-full flex items-center justify-between p-3 bg-gray-800/30 rounded-lg hover:bg-gray-800/50 transition-colors"
                >
                    <div className="flex items-center gap-2">
                        <Info className="w-4 h-4 text-blue-400" />
                        <span className="text-sm text-white font-medium">Hotel Policies & Information</span>
                    </div>
                    {isExpanded ? (
                        <ChevronUp className="w-4 h-4 text-gray-400" />
                    ) : (
                        <ChevronDown className="w-4 h-4 text-gray-400" />
                    )}
                </button>

                {isExpanded && (
                    <div className="mt-2 p-4 bg-gray-800/20 rounded-lg space-y-3 text-sm">
                        {policy.cancellationTimeline && (
                            <div className="flex gap-2">
                                <AlertCircle className="w-4 h-4 text-yellow-400 flex-shrink-0 mt-0.5" />
                                <div>
                                    <p className="text-gray-400 text-xs mb-1">Cancellation Policy</p>
                                    <p className="text-gray-200">{policy.cancellationTimeline}</p>
                                </div>
                            </div>
                        )}

                        {policy.checkInTime && (
                            <div className="flex gap-2">
                                <Clock className="w-4 h-4 text-blue-400 flex-shrink-0 mt-0.5" />
                                <div>
                                    <p className="text-gray-400 text-xs mb-1">Check-in / Check-out</p>
                                    <p className="text-gray-200">
                                        {policy.checkInTime} / {policy.checkOutTime || 'Standard checkout'}
                                    </p>
                                </div>
                            </div>
                        )}

                        {policy.hotelPolicies && policy.hotelPolicies.length > 0 && (
                            <div className="flex gap-2">
                                <Info className="w-4 h-4 text-gray-400 flex-shrink-0 mt-0.5" />
                                <div>
                                    <p className="text-gray-400 text-xs mb-1">Hotel Policies</p>
                                    <ul className="text-gray-200 space-y-1">
                                        {policy.hotelPolicies.map((p, idx) => (
                                            <li key={idx}>• {p}</li>
                                        ))}
                                    </ul>
                                </div>
                            </div>
                        )}
                    </div>
                )}
            </div>
        );
    }

    return (
        <div className="hotel-policy-display space-y-4">
            <div className="flex items-center gap-2 mb-3">
                <Info className="w-5 h-5 text-blue-400" />
                <h3 className="text-lg font-semibold text-white">Policies & Information</h3>
            </div>

            {/* Cancellation Policy */}
            {policy.cancellationTimeline && (
                <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-4">
                    <div className="flex items-start gap-3">
                        <AlertCircle className="w-5 h-5 text-yellow-400 flex-shrink-0 mt-0.5" />
                        <div>
                            <h4 className="text-yellow-400 font-semibold mb-1">Cancellation Policy</h4>
                            <p className="text-gray-300 text-sm">{policy.cancellationTimeline}</p>
                        </div>
                    </div>
                </div>
            )}

            {/* Check-in/Check-out Times */}
            {(policy.checkInTime || policy.checkOutTime) && (
                <div className="bg-gray-800/30 rounded-lg p-4">
                    <div className="flex items-start gap-3">
                        <Clock className="w-5 h-5 text-blue-400 flex-shrink-0 mt-0.5" />
                        <div className="flex-1">
                            <h4 className="text-white font-semibold mb-2">Check-in & Check-out</h4>
                            <div className="grid grid-cols-2 gap-4 text-sm">
                                {policy.checkInTime && (
                                    <div>
                                        <p className="text-gray-400 mb-1">Check-in</p>
                                        <p className="text-gray-200">{policy.checkInTime}</p>
                                    </div>
                                )}
                                {policy.checkOutTime && (
                                    <div>
                                        <p className="text-gray-400 mb-1">Check-out</p>
                                        <p className="text-gray-200">{policy.checkOutTime}</p>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Check-in Instructions */}
            {policy.checkInInstructions && (
                <div className="bg-gray-800/30 rounded-lg p-4">
                    <div className="flex items-start gap-3">
                        <Calendar className="w-5 h-5 text-green-400 flex-shrink-0 mt-0.5" />
                        <div>
                            <h4 className="text-white font-semibold mb-1">Check-in Instructions</h4>
                            <p className="text-gray-300 text-sm">{policy.checkInInstructions}</p>
                        </div>
                    </div>
                </div>
            )}

            {/* Key Collection */}
            {policy.keyCollectionInfo && (
                <div className="bg-gray-800/30 rounded-lg p-4">
                    <div className="flex items-start gap-3">
                        <Key className="w-5 h-5 text-purple-400 flex-shrink-0 mt-0.5" />
                        <div>
                            <h4 className="text-white font-semibold mb-1">Key Collection</h4>
                            <p className="text-gray-300 text-sm">{policy.keyCollectionInfo}</p>
                        </div>
                    </div>
                </div>
            )}

            {/* Hotel Policies */}
            {policy.hotelPolicies && policy.hotelPolicies.length > 0 && (
                <div className="bg-gray-800/30 rounded-lg p-4">
                    <h4 className="text-white font-semibold mb-2">Hotel Policies</h4>
                    <ul className="space-y-2 text-sm text-gray-300">
                        {policy.hotelPolicies.map((p, idx) => (
                            <li key={idx} className="flex items-start gap-2">
                                <span className="text-blue-400 mt-1">•</span>
                                <span>{p}</span>
                            </li>
                        ))}
                    </ul>
                </div>
            )}

            {/* Rate Conditions */}
            {policy.rateConditions && policy.rateConditions.length > 0 && (
                <div className="bg-gray-800/30 rounded-lg p-4">
                    <h4 className="text-white font-semibold mb-2">Rate Conditions</h4>
                    <ul className="space-y-2 text-sm text-gray-300">
                        {policy.rateConditions.map((condition, idx) => (
                            <li key={idx} className="flex items-start gap-2">
                                <span className="text-green-400 mt-1">•</span>
                                <span>{condition}</span>
                            </li>
                        ))}
                    </ul>
                </div>
            )}
        </div>
    );
};

export default HotelPolicyDisplay;
