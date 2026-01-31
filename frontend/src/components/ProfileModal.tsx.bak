import React, { useState, useEffect } from 'react';
import { X, Save, User, CreditCard, ShieldCheck } from 'lucide-react';
import axios from 'axios';

interface ProfileModalProps {
    isOpen: boolean;
    onClose: () => void;
}

export const ProfileModal: React.FC<ProfileModalProps> = ({ isOpen, onClose }) => {
    const [formData, setFormData] = useState({
        legal_first_name: '',
        legal_last_name: '',
        dob: '',
        passport_number: '',
        passport_expiry: '',
        passport_country: '',
        known_traveler_number: '',
        seat_preference: 'ANY',
        seat_position_preference: 'WINDOW', // NEW: TOP/MIDDLE/BOTTOM
        baggage_preference: 'CARRY_ON',
        hotel_preference: '4_STAR',
        flight_class_preference: 'ECONOMY',
        preferred_airline: '', // NEW: IATA code
        preferred_hotel_chains: '', // NEW: Comma-separated
        email: '',
        phone_number: ''
    });
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        if (isOpen) {
            fetchProfile();
        }
    }, [isOpen]);

    const fetchProfile = async () => {
        try {
            const res = await axios.get('http://localhost:8000/v1/profile/demo-user');
            if (res.data) {
                setFormData(prev => ({
                    ...prev,
                    ...res.data,
                    // Ensure no nulls to prevent uncontrolled input warning
                    legal_first_name: res.data.legal_first_name || '',
                    legal_last_name: res.data.legal_last_name || '',
                    dob: res.data.dob || '',
                    passport_number: res.data.passport_number || '',
                    passport_expiry: res.data.passport_expiry || '',
                    passport_country: res.data.passport_country || '',
                    known_traveler_number: res.data.known_traveler_number || '',
                    seat_position_preference: res.data.seat_position_preference || 'WINDOW',
                    preferred_airline: res.data.preferred_airline || '',
                    preferred_hotel_chains: res.data.preferred_hotel_chains || '',
                    email: res.data.email || '',
                    phone_number: res.data.phone_number || ''
                }));
            }
        } catch (e) {
            console.error("Failed to fetch profile", e);
        }
    };

    const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
        setFormData({ ...formData, [e.target.name]: e.target.value });
    };

    const handleSave = async () => {
        setLoading(true);
        try {
            await axios.put('http://localhost:8000/v1/profile/demo-user', formData);
            alert("Profile Saved!");
            onClose();
        } catch (e) {
            alert("Failed to save profile");
        } finally {
            setLoading(false);
        }
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
            <div className="bg-card border border-white/10 w-full max-w-2xl rounded-3xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200 flex flex-col max-h-[90vh]">

                {/* Header */}
                <div className="bg-gradient-to-r from-gray-800 to-gray-900 p-6 text-white relative flex items-center justify-between border-b border-white/5">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-primary/20 flex items-center justify-center text-primary">
                            <User size={20} />
                        </div>
                        <div>
                            <h2 className="text-xl font-bold">Traveler Profile</h2>
                            <p className="text-sm text-gray-400">Manage your identity & preferences</p>
                        </div>
                    </div>
                    <button onClick={onClose} className="p-2 hover:bg-white/10 rounded-full transition-colors">
                        <X size={20} />
                    </button>
                </div>

                {/* Form Content */}
                <div className="p-6 overflow-y-auto space-y-6 custom-scrollbar">

                    {/* Identity Section */}
                    <div className="space-y-4">
                        <div className="flex items-center gap-2 text-primary font-medium border-b border-white/5 pb-2">
                            <ShieldCheck size={18} />
                            <h3>Identity Documents</h3>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div className="space-y-1">
                                <label className="text-xs text-gray-400 uppercase font-medium">First Name</label>
                                <input name="legal_first_name" value={formData.legal_first_name} onChange={handleChange} className="glass-input w-full" placeholder="As on passport" />
                            </div>
                            <div className="space-y-1">
                                <label className="text-xs text-gray-400 uppercase font-medium">Last Name</label>
                                <input name="legal_last_name" value={formData.legal_last_name} onChange={handleChange} className="glass-input w-full" placeholder="As on passport" />
                            </div>
                            <div className="space-y-1">
                                <label className="text-xs text-gray-400 uppercase font-medium">Date of Birth</label>
                                <input type="date" name="dob" value={formData.dob} onChange={handleChange} className="glass-input w-full" />
                            </div>
                            <div className="space-y-1">
                                <label className="text-xs text-gray-400 uppercase font-medium">Known Traveler #</label>
                                <input name="known_traveler_number" value={formData.known_traveler_number} onChange={handleChange} className="glass-input w-full" placeholder="TSA PreCheck / Global Entry" />
                            </div>
                        </div>
                    </div>

                    {/* Contact Section */}
                    <div className="space-y-4">
                        <div className="flex items-center gap-2 text-primary font-medium border-b border-white/5 pb-2">
                            <User size={18} />
                            <h3>Contact Details</h3>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div className="space-y-1">
                                <label className="text-xs text-gray-400 uppercase font-medium">Email</label>
                                <input type="email" name="email" value={formData.email} onChange={handleChange} className="glass-input w-full" placeholder="you@example.com" />
                            </div>
                            <div className="space-y-1">
                                <label className="text-xs text-gray-400 uppercase font-medium">Phone Number</label>
                                <input type="tel" name="phone_number" value={formData.phone_number} onChange={handleChange} className="glass-input w-full" placeholder="+1 555 555 5555" />
                            </div>
                        </div>
                    </div>

                    {/* Passport Section */}
                    <div className="space-y-4">
                        <div className="flex items-center gap-2 text-primary font-medium border-b border-white/5 pb-2">
                            <CreditCard size={18} />
                            <h3>Passport Details</h3>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                            <div className="space-y-1 md:col-span-1">
                                <label className="text-xs text-gray-400 uppercase font-medium">Country</label>
                                <input name="passport_country" value={formData.passport_country} onChange={handleChange} className="glass-input w-full" placeholder="US" maxLength={2} />
                            </div>
                            <div className="space-y-1 md:col-span-1">
                                <label className="text-xs text-gray-400 uppercase font-medium">Passport Number</label>
                                <input name="passport_number" value={formData.passport_number} onChange={handleChange} className="glass-input w-full" placeholder="XXXXXXXX" />
                            </div>
                            <div className="space-y-1 md:col-span-1">
                                <label className="text-xs text-gray-400 uppercase font-medium">Expiry Date</label>
                                <input type="date" name="passport_expiry" value={formData.passport_expiry} onChange={handleChange} className="glass-input w-full" />
                            </div>
                        </div>
                    </div>

                    {/* Preferences Section */}
                    <div className="space-y-4">
                        <div className="flex items-center gap-2 text-primary font-medium border-b border-white/5 pb-2">
                            <User size={18} />
                            <h3>Preferences</h3>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div className="space-y-1">
                                <label className="text-xs text-gray-400 uppercase font-medium">Seat Preference</label>
                                <select name="seat_preference" value={formData.seat_preference} onChange={handleChange} className="glass-input w-full bg-black/20">
                                    <option value="ANY">Any Seat</option>
                                    <option value="WINDOW">Window (Ventana)</option>
                                    <option value="MIDDLE">Middle (Medio)</option>
                                    <option value="AISLE">Aisle (Pasillo)</option>
                                </select>
                            </div>
                            <div className="space-y-1">
                                <label className="text-xs text-gray-400 uppercase font-medium">Seat Position</label>
                                <select name="seat_position_preference" value={formData.seat_position_preference || 'WINDOW'} onChange={handleChange} className="glass-input w-full bg-black/20">
                                    <option value="TOP">Top (Arriba)</option>
                                    <option value="MIDDLE">Middle (Medio)</option>
                                    <option value="BOTTOM">Bottom (Abajo)</option>
                                </select>
                            </div>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
                            <div className="space-y-1">
                                <label className="text-xs text-gray-400 uppercase font-medium">Baggage Preference</label>
                                <select name="baggage_preference" value={formData.baggage_preference} onChange={handleChange} className="glass-input w-full bg-black/20">
                                    <option value="CARRY_ON">Carry-on Only</option>
                                    <option value="CHECKED_1">1 Checked Bag</option>
                                    <option value="CHECKED_2">2 Checked Bags</option>
                                </select>
                            </div>
                            <div className="space-y-1">
                                <label className="text-xs text-gray-400 uppercase font-medium">Preferred Airline</label>
                                <input name="preferred_airline" value={formData.preferred_airline || ''} onChange={handleChange} className="glass-input w-full" placeholder="AM, AA, DL..." maxLength={2} />
                            </div>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
                            <div className="space-y-1">
                                <label className="text-xs text-gray-400 uppercase font-medium">Hotel Preference</label>
                                <select name="hotel_preference" value={formData.hotel_preference || '4_STAR'} onChange={handleChange} className="glass-input w-full bg-black/20">
                                    <option value="3_STAR">3 Stars</option>
                                    <option value="4_STAR">4 Stars</option>
                                    <option value="5_STAR">5 Stars (Luxury)</option>
                                </select>
                            </div>
                            <div className="space-y-1">
                                <label className="text-xs text-gray-400 uppercase font-medium">Flight Class</label>
                                <select name="flight_class_preference" value={formData.flight_class_preference || 'ECONOMY'} onChange={handleChange} className="glass-input w-full bg-black/20">
                                    <option value="ECONOMY">Economy</option>
                                    <option value="PREMIUM_ECONOMY">Premium Economy</option>
                                    <option value="BUSINESS">Business Class</option>
                                    <option value="FIRST">First Class</option>
                                </select>
                            </div>
                        </div>

                        <div className="space-y-1 mt-4">
                            <label className="text-xs text-gray-400 uppercase font-medium">Preferred Hotel Chains</label>
                            <input name="preferred_hotel_chains" value={formData.preferred_hotel_chains || ''} onChange={handleChange} className="glass-input w-full" placeholder="Marriott, Hilton, Hyatt..." />
                            <p className="text-xs text-gray-500">Comma-separated (ej. Marriott,Hilton)</p>
                        </div>
                    </div>

                </div>

                {/* Footer */}
                <div className="p-6 border-t border-white/5 bg-black/20 flex justify-end gap-3">
                    <button onClick={onClose} className="px-6 py-2 rounded-xl text-sm font-medium hover:bg-white/5 transition-colors">
                        Cancel
                    </button>
                    <button
                        onClick={handleSave}
                        disabled={loading}
                        className="px-6 py-2 bg-primary hover:bg-primary/90 text-white rounded-xl text-sm font-bold shadow-lg shadow-primary/20 transition-all flex items-center gap-2"
                    >
                        {loading ? "Saving..." : <><Save size={16} /> Save Profile</>}
                    </button>
                </div>
            </div>
        </div>
    );
};
