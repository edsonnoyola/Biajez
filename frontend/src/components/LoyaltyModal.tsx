import React, { useState, useEffect } from 'react';
import { X, Plane, Plus, Trash2, Award, AlertCircle } from 'lucide-react';
import axios from 'axios';
import API_URL from '../config/api';

interface LoyaltyProgram {
    airline_code: string;
    program_name: string;
    member_number: string;
    tier: string | null;
    airline: string;
}

interface LoyaltyModalProps {
    isOpen: boolean;
    onClose: () => void;
    userId: string;
}

const AIRLINES = [
    { code: 'AM', name: 'Aeroméxico', program: 'Club Premier' },
    { code: 'AA', name: 'American Airlines', program: 'AAdvantage' },
    { code: 'UA', name: 'United Airlines', program: 'MileagePlus' },
    { code: 'DL', name: 'Delta Air Lines', program: 'SkyMiles' },
    { code: 'IB', name: 'Iberia', program: 'Iberia Plus' },
    { code: 'BA', name: 'British Airways', program: 'Executive Club' },
    { code: 'AF', name: 'Air France', program: 'Flying Blue' },
    { code: 'LH', name: 'Lufthansa', program: 'Miles & More' },
    { code: 'Y4', name: 'Volaris', program: 'V.Club' },
    { code: 'VB', name: 'VivaAerobus', program: 'Viajero Frecuente' },
];

export const LoyaltyModal: React.FC<LoyaltyModalProps> = ({ isOpen, onClose, userId }) => {
    const [programs, setPrograms] = useState<LoyaltyProgram[]>([]);
    const [loading, setLoading] = useState(false);
    const [showAddForm, setShowAddForm] = useState(false);
    const [newProgram, setNewProgram] = useState({
        airline_code: '',
        member_number: '',
        tier: ''
    });
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        if (isOpen) {
            fetchPrograms();
        }
    }, [isOpen]);

    const fetchPrograms = async () => {
        setLoading(true);
        try {
            const response = await axios.get(`${API_URL}/api/loyalty/${userId}`);
            setPrograms(response.data || []);
        } catch (error) {
            console.error('Error fetching loyalty programs:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleAdd = async () => {
        if (!newProgram.airline_code || !newProgram.member_number) return;

        setSaving(true);
        try {
            await axios.post(`${API_URL}/api/loyalty/`, {
                user_id: userId,
                airline_code: newProgram.airline_code,
                member_number: newProgram.member_number,
                tier: newProgram.tier || null
            });
            setNewProgram({ airline_code: '', member_number: '', tier: '' });
            setShowAddForm(false);
            fetchPrograms();
        } catch (error) {
            console.error('Error adding program:', error);
            alert('Error al agregar programa');
        } finally {
            setSaving(false);
        }
    };

    const handleDelete = async (airlineCode: string) => {
        if (!confirm('¿Eliminar este programa de millas?')) return;

        try {
            await axios.delete(`${API_URL}/api/loyalty/${userId}/${airlineCode}`);
            fetchPrograms();
        } catch (error) {
            console.error('Error deleting program:', error);
        }
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
            <div className="bg-gray-900/95 backdrop-blur-xl border border-white/10 w-full max-w-2xl rounded-3xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200 flex flex-col max-h-[90vh]">

                {/* Header */}
                <div className="bg-gradient-to-r from-purple-900 to-gray-900 p-6 text-white relative flex items-center justify-between border-b border-white/5">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-purple-500/20 flex items-center justify-center text-purple-400">
                            <Award size={20} />
                        </div>
                        <div>
                            <h2 className="text-xl font-bold">Programas de Millas</h2>
                            <p className="text-sm text-gray-400">
                                {programs.length} programa{programs.length !== 1 ? 's' : ''} registrado{programs.length !== 1 ? 's' : ''}
                            </p>
                        </div>
                    </div>
                    <button onClick={onClose} className="p-2 hover:bg-white/10 rounded-full transition-colors">
                        <X size={20} />
                    </button>
                </div>

                {/* Content */}
                <div className="p-6 overflow-y-auto custom-scrollbar flex-1">
                    {loading ? (
                        <div className="text-center py-8">
                            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-500 mx-auto"></div>
                            <p className="text-gray-400 mt-2">Cargando programas...</p>
                        </div>
                    ) : (
                        <>
                            {/* Programs List */}
                            {programs.length === 0 && !showAddForm ? (
                                <div className="text-center py-12">
                                    <Plane className="mx-auto text-gray-600 mb-4" size={48} />
                                    <p className="text-gray-400">No tienes programas de millas registrados</p>
                                    <p className="text-sm text-gray-500 mt-2">
                                        Agrega tus números para acumular millas automáticamente
                                    </p>
                                </div>
                            ) : (
                                <div className="space-y-3 mb-6">
                                    {programs.map((program) => (
                                        <div
                                            key={program.airline_code}
                                            className="bg-white/5 border border-purple-500/30 rounded-xl p-4 hover:bg-white/10 transition-colors"
                                        >
                                            <div className="flex items-center justify-between">
                                                <div className="flex items-center gap-4">
                                                    <span className="px-3 py-1 bg-purple-500/20 text-purple-400 rounded-full text-sm font-mono font-bold">
                                                        {program.airline_code}
                                                    </span>
                                                    <div>
                                                        <p className="font-semibold text-white">{program.airline}</p>
                                                        <p className="text-sm text-gray-400">{program.program_name}</p>
                                                    </div>
                                                </div>
                                                <div className="flex items-center gap-4">
                                                    <div className="text-right">
                                                        <p className="font-mono text-purple-300">{program.member_number}</p>
                                                        {program.tier && (
                                                            <span className="text-xs text-yellow-400">{program.tier}</span>
                                                        )}
                                                    </div>
                                                    <button
                                                        onClick={() => handleDelete(program.airline_code)}
                                                        className="p-2 hover:bg-red-500/20 rounded-lg text-red-400 transition-colors"
                                                    >
                                                        <Trash2 size={16} />
                                                    </button>
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}

                            {/* Add Form */}
                            {showAddForm ? (
                                <div className="bg-white/5 border border-white/10 rounded-xl p-4 space-y-4">
                                    <h3 className="font-semibold text-white">Agregar Programa</h3>

                                    <div className="space-y-1">
                                        <label className="text-xs text-gray-400 uppercase">Aerolínea</label>
                                        <select
                                            value={newProgram.airline_code}
                                            onChange={(e) => setNewProgram({ ...newProgram, airline_code: e.target.value })}
                                            className="glass-input w-full bg-black/20"
                                        >
                                            <option value="">Seleccionar aerolínea...</option>
                                            {AIRLINES.map((airline) => (
                                                <option key={airline.code} value={airline.code}>
                                                    {airline.name} - {airline.program}
                                                </option>
                                            ))}
                                        </select>
                                    </div>

                                    <div className="space-y-1">
                                        <label className="text-xs text-gray-400 uppercase">Número de Miembro</label>
                                        <input
                                            type="text"
                                            value={newProgram.member_number}
                                            onChange={(e) => setNewProgram({ ...newProgram, member_number: e.target.value })}
                                            className="glass-input w-full"
                                            placeholder="123456789"
                                        />
                                    </div>

                                    <div className="space-y-1">
                                        <label className="text-xs text-gray-400 uppercase">Nivel/Tier (opcional)</label>
                                        <input
                                            type="text"
                                            value={newProgram.tier}
                                            onChange={(e) => setNewProgram({ ...newProgram, tier: e.target.value })}
                                            className="glass-input w-full"
                                            placeholder="Gold, Platinum, etc."
                                        />
                                    </div>

                                    <div className="flex gap-3 pt-2">
                                        <button
                                            onClick={() => setShowAddForm(false)}
                                            className="flex-1 px-4 py-2 rounded-xl text-sm hover:bg-white/5 transition-colors"
                                        >
                                            Cancelar
                                        </button>
                                        <button
                                            onClick={handleAdd}
                                            disabled={saving || !newProgram.airline_code || !newProgram.member_number}
                                            className="flex-1 px-4 py-2 bg-purple-500 hover:bg-purple-600 disabled:opacity-50 text-white rounded-xl text-sm font-bold transition-colors"
                                        >
                                            {saving ? 'Guardando...' : 'Guardar'}
                                        </button>
                                    </div>
                                </div>
                            ) : (
                                <button
                                    onClick={() => setShowAddForm(true)}
                                    className="w-full py-3 border-2 border-dashed border-white/20 rounded-xl text-gray-400 hover:border-purple-500/50 hover:text-purple-400 transition-colors flex items-center justify-center gap-2"
                                >
                                    <Plus size={20} />
                                    Agregar Programa de Millas
                                </button>
                            )}
                        </>
                    )}
                </div>

                {/* Footer */}
                <div className="p-4 border-t border-white/5 bg-gray-900/50">
                    <div className="flex items-start gap-2 text-xs text-gray-400">
                        <AlertCircle size={14} className="flex-shrink-0 mt-0.5" />
                        <p>
                            Tus números de viajero frecuente se aplicarán automáticamente en futuras reservas con la aerolínea correspondiente.
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
};
