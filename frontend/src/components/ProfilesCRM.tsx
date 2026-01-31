import { useState, useEffect } from 'react';
import { X, Search, UserCircle, Plane, Hotel, Edit2, Trash2, ChevronLeft, ChevronRight } from 'lucide-react';
import API_URL from '../config/api';

interface Profile {
    user_id: string;
    name: string;
    email: string | null;
    phone_number: string | null;
    seat_preference: string;
    flight_class_preference: string;
    hotel_preference: string;
    preferred_airline: string | null;
}

interface ProfilesCRMProps {
    isOpen: boolean;
    onClose: () => void;
}

export function ProfilesCRM({ isOpen, onClose }: ProfilesCRMProps) {
    const [profiles, setProfiles] = useState<Profile[]>([]);
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState('');
    const [editingProfile, setEditingProfile] = useState<Profile | null>(null);
    const [total, setTotal] = useState(0);
    const [page, setPage] = useState(0);
    const limit = 10;

    const fetchProfiles = async () => {
        setLoading(true);
        try {
            const params = new URLSearchParams({
                limit: limit.toString(),
                offset: (page * limit).toString(),
            });
            if (search) params.append('search', search);

            const res = await fetch(`${API_URL}/v1/profiles?${params}`);
            const data = await res.json();
            setProfiles(data.profiles || []);
            setTotal(data.total || 0);
        } catch (err) {
            console.error('Error fetching profiles:', err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (isOpen) {
            fetchProfiles();
        }
    }, [isOpen, page, search]);

    const handleDelete = async (userId: string) => {
        if (!confirm('¿Eliminar este perfil?')) return;
        try {
            await fetch(`${API_URL}/v1/profiles/${userId}`, { method: 'DELETE' });
            fetchProfiles();
        } catch (err) {
            console.error('Error deleting:', err);
        }
    };

    const handleSave = async (profile: Profile) => {
        try {
            await fetch(`${API_URL}/v1/profile/${profile.user_id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    seat_preference: profile.seat_preference,
                    flight_class_preference: profile.flight_class_preference,
                    hotel_preference: profile.hotel_preference,
                    preferred_airline: profile.preferred_airline,
                }),
            });
            setEditingProfile(null);
            fetchProfiles();
        } catch (err) {
            console.error('Error saving:', err);
        }
    };

    if (!isOpen) return null;

    const seatIcons: Record<string, string> = {
        WINDOW: '🪟',
        AISLE: '🚶',
        MIDDLE: '👤',
        ANY: '✨',
    };

    const classIcons: Record<string, string> = {
        ECONOMY: '💺',
        PREMIUM_ECONOMY: '💺✨',
        BUSINESS: '🛋️',
        FIRST: '👑',
    };

    return (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <div className="bg-surface-dark border border-white/10 rounded-2xl w-full max-w-5xl max-w-[90vw] max-h-[90vh] overflow-hidden flex flex-col">
                {/* Header */}
                <div className="p-6 border-b border-white/10 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <UserCircle className="text-primary" size={28} />
                        <h2 className="text-xl font-bold">CRM de Perfiles</h2>
                        <span className="text-white/50 text-sm">({total} usuarios)</span>
                    </div>
                    <button onClick={onClose} className="p-2 hover:bg-white/10 rounded-lg transition-colors">
                        <X size={20} />
                    </button>
                </div>

                {/* Search */}
                <div className="p-4 border-b border-white/5">
                    <div className="relative">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-white/40" size={18} />
                        <input
                            type="text"
                            placeholder="Buscar por nombre, email o teléfono..."
                            value={search}
                            onChange={(e) => {
                                setSearch(e.target.value);
                                setPage(0);
                            }}
                            className="w-full bg-white/5 border border-white/10 rounded-xl pl-10 pr-4 py-3 focus:outline-none focus:border-primary/50"
                        />
                    </div>
                </div>

                {/* Table */}
                <div className="flex-1 overflow-auto">
                    {loading ? (
                        <div className="flex items-center justify-center py-12">
                            <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                        </div>
                    ) : profiles.length === 0 ? (
                        <div className="text-center py-12 text-white/50">
                            No se encontraron perfiles
                        </div>
                    ) : (
                        <table className="w-full">
                            <thead className="bg-white/5 sticky top-0">
                                <tr className="text-left text-white/60 text-sm">
                                    <th className="px-4 py-3">Usuario</th>
                                    <th className="px-4 py-3">Contacto</th>
                                    <th className="px-4 py-3 text-center">
                                        <Plane size={16} className="inline" /> Vuelo
                                    </th>
                                    <th className="px-4 py-3 text-center">
                                        <Hotel size={16} className="inline" /> Hotel
                                    </th>
                                    <th className="px-4 py-3 text-center">Acciones</th>
                                </tr>
                            </thead>
                            <tbody>
                                {profiles.map((profile) => (
                                    <tr key={profile.user_id} className="border-b border-white/5 hover:bg-white/5 transition-colors">
                                        <td className="px-4 py-4">
                                            <div className="font-medium">{profile.name || 'Sin nombre'}</div>
                                            <div className="text-xs text-white/40 font-mono">{profile.user_id.slice(0, 8)}...</div>
                                        </td>
                                        <td className="px-4 py-4">
                                            <div className="text-sm">{profile.email || '-'}</div>
                                            <div className="text-sm text-white/50">{profile.phone_number || '-'}</div>
                                        </td>
                                        <td className="px-4 py-4 text-center">
                                            <div className="text-lg">{seatIcons[profile.seat_preference] || '✨'}</div>
                                            <div className="text-xs text-white/50">{classIcons[profile.flight_class_preference] || '💺'} {profile.flight_class_preference}</div>
                                        </td>
                                        <td className="px-4 py-4 text-center">
                                            <div className="text-sm">{profile.hotel_preference?.replace('_', ' ') || '4 STAR'}</div>
                                        </td>
                                        <td className="px-4 py-4 text-center">
                                            <button
                                                onClick={() => setEditingProfile(profile)}
                                                className="p-2 hover:bg-primary/20 rounded-lg transition-colors text-primary"
                                            >
                                                <Edit2 size={16} />
                                            </button>
                                            <button
                                                onClick={() => handleDelete(profile.user_id)}
                                                className="p-2 hover:bg-red-500/20 rounded-lg transition-colors text-red-400 ml-1"
                                            >
                                                <Trash2 size={16} />
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    )}
                </div>

                {/* Pagination */}
                <div className="p-4 border-t border-white/10 flex items-center justify-between">
                    <div className="text-sm text-white/50">
                        Mostrando {page * limit + 1}-{Math.min((page + 1) * limit, total)} de {total}
                    </div>
                    <div className="flex gap-2">
                        <button
                            onClick={() => setPage(Math.max(0, page - 1))}
                            disabled={page === 0}
                            className="p-2 bg-white/5 rounded-lg hover:bg-white/10 disabled:opacity-30"
                        >
                            <ChevronLeft size={18} />
                        </button>
                        <button
                            onClick={() => setPage(page + 1)}
                            disabled={(page + 1) * limit >= total}
                            className="p-2 bg-white/5 rounded-lg hover:bg-white/10 disabled:opacity-30"
                        >
                            <ChevronRight size={18} />
                        </button>
                    </div>
                </div>
            </div>

            {/* Edit Modal */}
            {editingProfile && (
                <div className="fixed inset-0 bg-black/60 z-60 flex items-center justify-center p-4">
                    <div className="bg-surface-dark border border-white/10 rounded-2xl p-6 w-full max-w-md">
                        <h3 className="text-lg font-bold mb-4">Editar Preferencias</h3>
                        <div className="space-y-4">
                            <div>
                                <label className="text-sm text-white/60 block mb-1">Asiento</label>
                                <select
                                    value={editingProfile.seat_preference}
                                    onChange={(e) => setEditingProfile({ ...editingProfile, seat_preference: e.target.value })}
                                    className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2"
                                >
                                    <option value="WINDOW">🪟 Ventana</option>
                                    <option value="AISLE">🚶 Pasillo</option>
                                    <option value="MIDDLE">👤 Medio</option>
                                    <option value="ANY">✨ Cualquiera</option>
                                </select>
                            </div>
                            <div>
                                <label className="text-sm text-white/60 block mb-1">Clase de Vuelo</label>
                                <select
                                    value={editingProfile.flight_class_preference}
                                    onChange={(e) => setEditingProfile({ ...editingProfile, flight_class_preference: e.target.value })}
                                    className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2"
                                >
                                    <option value="ECONOMY">💺 Economy</option>
                                    <option value="PREMIUM_ECONOMY">💺✨ Premium Economy</option>
                                    <option value="BUSINESS">🛋️ Business</option>
                                    <option value="FIRST">👑 First</option>
                                </select>
                            </div>
                            <div>
                                <label className="text-sm text-white/60 block mb-1">Hotel Preferido</label>
                                <select
                                    value={editingProfile.hotel_preference}
                                    onChange={(e) => setEditingProfile({ ...editingProfile, hotel_preference: e.target.value })}
                                    className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2"
                                >
                                    <option value="3_STAR">⭐⭐⭐ 3 Estrellas</option>
                                    <option value="4_STAR">⭐⭐⭐⭐ 4 Estrellas</option>
                                    <option value="5_STAR">⭐⭐⭐⭐⭐ 5 Estrellas</option>
                                </select>
                            </div>
                            <div>
                                <label className="text-sm text-white/60 block mb-1">Aerolínea Preferida</label>
                                <input
                                    type="text"
                                    value={editingProfile.preferred_airline || ''}
                                    onChange={(e) => setEditingProfile({ ...editingProfile, preferred_airline: e.target.value })}
                                    placeholder="Código IATA (ej: AM, AA)"
                                    className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-2"
                                />
                            </div>
                        </div>
                        <div className="flex gap-3 mt-6">
                            <button
                                onClick={() => setEditingProfile(null)}
                                className="flex-1 py-3 bg-white/10 rounded-xl hover:bg-white/20 transition-colors"
                            >
                                Cancelar
                            </button>
                            <button
                                onClick={() => handleSave(editingProfile)}
                                className="flex-1 py-3 bg-primary rounded-xl hover:bg-primary/80 transition-colors font-medium"
                            >
                                Guardar
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
