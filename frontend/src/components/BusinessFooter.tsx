import React from 'react';
import { Mail, Phone, MapPin, FileText, Shield } from 'lucide-react';

interface BusinessFooterProps {
    variant?: 'full' | 'compact';
}

export const BusinessFooter: React.FC<BusinessFooterProps> = ({ variant = 'full' }) => {
    const businessInfo = {
        name: 'Biajez',
        address: 'Mexico City, Mexico',
        email: 'support@biajez.com',
        phone: '+52 55 1234 5678',
        termsUrl: '/terms',
        privacyUrl: '/privacy',
    };

    if (variant === 'compact') {
        return (
            <div className="business-footer-compact text-xs text-gray-500 border-t border-gray-800 pt-3 mt-4">
                <p className="mb-1">
                    Operated by <span className="text-gray-400 font-medium">{businessInfo.name}</span>
                </p>
                <p>
                    Questions? Contact us at{' '}
                    <a href={`mailto:${businessInfo.email}`} className="text-blue-400 hover:text-blue-300">
                        {businessInfo.email}
                    </a>
                </p>
            </div>
        );
    }

    return (
        <div className="business-footer bg-gray-900/50 rounded-lg p-6 mt-6 border border-gray-800">
            <div className="grid md:grid-cols-2 gap-6">
                {/* Company Info */}
                <div>
                    <h4 className="text-white font-semibold mb-3 flex items-center gap-2">
                        <img src="/logo.svg" alt="Biajez" className="w-6 h-6" />
                        {businessInfo.name}
                    </h4>
                    <div className="space-y-2 text-sm">
                        <div className="flex items-start gap-2 text-gray-400">
                            <MapPin className="w-4 h-4 mt-0.5 flex-shrink-0" />
                            <span>{businessInfo.address}</span>
                        </div>
                    </div>
                </div>

                {/* Contact Info */}
                <div>
                    <h4 className="text-white font-semibold mb-3">Customer Service</h4>
                    <div className="space-y-2 text-sm">
                        <div className="flex items-center gap-2 text-gray-400">
                            <Mail className="w-4 h-4 flex-shrink-0" />
                            <a
                                href={`mailto:${businessInfo.email}`}
                                className="text-blue-400 hover:text-blue-300 transition-colors"
                            >
                                {businessInfo.email}
                            </a>
                        </div>
                        <div className="flex items-center gap-2 text-gray-400">
                            <Phone className="w-4 h-4 flex-shrink-0" />
                            <a
                                href={`tel:${businessInfo.phone}`}
                                className="text-blue-400 hover:text-blue-300 transition-colors"
                            >
                                {businessInfo.phone}
                            </a>
                        </div>
                    </div>
                </div>
            </div>

            {/* Legal Links */}
            <div className="mt-6 pt-4 border-t border-gray-800">
                <div className="flex flex-wrap gap-4 text-sm">
                    <a
                        href={businessInfo.termsUrl}
                        className="flex items-center gap-1.5 text-gray-400 hover:text-white transition-colors"
                    >
                        <FileText className="w-4 h-4" />
                        Terms & Conditions
                    </a>
                    <a
                        href={businessInfo.privacyUrl}
                        className="flex items-center gap-1.5 text-gray-400 hover:text-white transition-colors"
                    >
                        <Shield className="w-4 h-4" />
                        Privacy Policy
                    </a>
                    <a
                        href="https://www.booking.com/content/terms.html"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-1.5 text-gray-400 hover:text-white transition-colors"
                    >
                        <FileText className="w-4 h-4" />
                        Booking.com Terms
                    </a>
                </div>
                <p className="text-xs text-gray-600 mt-3">
                    © {new Date().getFullYear()} {businessInfo.name}. All rights reserved.
                </p>
            </div>
        </div>
    );
};

export default BusinessFooter;
