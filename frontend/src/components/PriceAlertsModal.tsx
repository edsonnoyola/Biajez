import React, { useState, useEffect } from 'react';
import { X, Bell, BellOff, TrendingDown, Plane, Trash2, Plus, AlertCircle } from 'lucide-react';
import axios from 'axios';
import API_URL from '../config/api';

interface PriceAlert {
    id: number;
    user_id: string;
    origin: string;
    destination: string;
    departure_date: string;
    return_date: string | null;
    target_price: number;
    current_price: number;
    lowest_price: number;
    is_active: boolean;
    notification_count: number;
}

interface PriceAlertsModalProps {
    isOpen: boolean;
    onClose: () => void;
    userId: string;
    phoneNumber?: string;
    // For creating new alert from current search
    currentSearch?: {
        origin: string;
        destination: string;
        departure_date: string;
        return_date?: string;
        current_price: number;
    };
}

export const PriceAlertsModal: React.FC<PriceAlertsModalProps> = ({
    isOpen,
    onClose,
    userId,
    phoneNumber,
    currentSearch
}) => {
    const [alerts, setAlerts] = useState<PriceAlert[]>([]);
    const [loading, setLoading] = useState(false);
    const [showCreateForm, setShowCreateForm] = useState(false);
    const [creating, setCreating] = useState(false);
    const [newAlert, setNewAlert] = useState({
        origin: currentSearch?.origin || '',
        destination: currentSearch?.destination || '',
        departure_date: currentSearch?.departure_date || '',
        return_date: currentSearch?.return_date || '',
        current_price: currentSearch?.current_price || 0,
        target_price: currentSearch ? Math.floor(currentSearch.current_price * 0.9) : 0
    });

    useEffect(() => {
        if (isOpen) {
            fetchAlerts();
            if (currentSearch) {
                setShowCreateForm(true);
                setNewAlert({
                    origin: currentSearch.origin,
                    destination: currentSearch.destination,
                    departure_date: currentSearch.departure_date,
                    return_date: currentSearch.return_date || '',
                    current_price: currentSearch.current_price,
                    target_price: Math.floor(currentSearch.current_price * 0.9)
                });
            }
        }
    }, [isOpen, currentSearch]);

    const fetchAlerts = async () => {
        setLoading(true);
        try {
            const response = await axios.get(`${API_URL}/api/price-alerts/${userId}`);
            setAlerts(response.data.alerts || []);
        } catch (error) {
            console.error('Error fetching alerts:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleCreate = async () => {
        if (!newAlert.origin || !newAlert.destination || !newAlert.departure_date) return;

        setCreating(true);
        try {
            await axios.post(`${API_URL}/api/price-alerts/`, {
                user_id: userId,
                phone_number: phoneNumber || '',
                search_type: 'flight',
                origin: newAlert.origin,
                destination: newAlert.destination,
                departure_date: newAlert.departure_date,
                return_date: newAlert.return_date || null,
                current_price: newAlert.current_price,
                target_price: newAlert.target_price
            });
            setShowCreateForm(false);
            setNewAlert({
                origin: '',
                destination: '',
                departure_date: '',
                return_date: '',
                current_price: 0,
                target_price: 0
            });
            fetchAlerts();
        } catch (error) {
            console.error('Error creating alert:', error);
            alert('Error al crear alerta');
        } finally {
            setCreating(false);
        }
    };

    const handleDelete = async (alertId: number) => {
        if (!confirm('¿Eliminar esta alerta de precio?')) return;

        try {
            await axios.delete(`${API_URL}/api/price-alerts/${alertId}`);
            fetchAlerts();
        } catch (error) {
            console.error('Error deleting alert:', error);
        }
    };

    const formatDate = (dateString: string) => {
        try {
            return new Date(dateString).toLocaleDateString('es-MX', {
                day: 'numeric',
                month: 'short'
            });
        } catch {
            return dateString;
        }
    };

    const getPriceChange = (alert: PriceAlert) => {
        const change = ((alert.current_price - alert.lowest_price) / alert.lowest_price * 100);
        return change;
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
            <div className="bg-gray-900/95 backdrop-blur-xl border border-white/10 w-full max-w-2xl rounded-3xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200 flex flex-col max-h-[90vh]">

                {/* Header */}
                <div className="bg-gradient-to-r from-orange-900 to-gray-900 p-6 text-white relative flex items-center justify-between border-b border-white/5">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-orange-500/20 flex items-center justify-center text-orange-400">
                            <Bell size={20} />
                        </div>
                        <div>
                            <h2 className="text-xl font-bold">Alertas de Precio</h2>
                            <p className="text-sm text-gray-400">
                                {alerts.filter(a => a.is_active).length} alerta{alerts.filter(a => a.is_active).length !== 1 ? 's' : ''} activa{alerts.filter(a => a.is_active).length !== 1 ? 's' : ''}
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
                            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-orange-500 mx-auto"></div>
                            <p className="text-gray-400 mt-2">Cargando alertas...</p>
                        </div>
                    ) : (
                        <>
                            {/* Create Form */}
                            {showCreateForm && (
                                <div className="bg-white/5 border border-orange-500/30 rounded-xl p-4 mb-6 space-y-4">
                                    <h3 className="font-semibold text-white flex items-center gap-2">
                                        <TrendingDown size={18} className="text-orange-400" />
                                        Nueva Alerta de Precio
                                    </h3>

                                    <div className="grid grid-cols-2 gap-4">
                                        <div className="space-y-1">
                                            <label className="text-xs text-gray-400 uppercase">Origen</label>
                                            <input
                                                type="text"
                                                value={newAlert.origin}
                                                onChange={(e) => setNewAlert({ ...newAlert, origin: e.target.value.toUpperCase() })}
                                                className="glass-input w-full"
                                                placeholder="MEX"
                                                maxLength={3}
                                            />
                                        </div>
                                        <div className="space-y-1">
                                            <label className="text-xs text-gray-400 uppercase">Destino</label>
                                            <input
                                                type="text"
                                                value={newAlert.destination}
                                                onChange={(e) => setNewAlert({ ...newAlert, destination: e.target.value.toUpperCase() })}
                                                className="glass-input w-full"
                                                placeholder="CUN"
                                                maxLength={3}
                                            />
                                        </div>
                                    </div>

                                    <div className="grid grid-cols-2 gap-4">
                                        <div className="space-y-1">
                                            <label className="text-xs text-gray-400 uppercase">Fecha Ida</label>
                                            <input
                                                type="date"
                                                value={newAlert.departure_date}
                                                onChange={(e) => setNewAlert({ ...newAlert, departure_date: e.target.value })}
                                                className="glass-input w-full"
                                            />
                                        </div>
                                        <div className="space-y-1">
                                            <label className="text-xs text-gray-400 uppercase">Fecha Vuelta (opcional)</label>
                                            <input
                                                type="date"
                                                value={newAlert.return_date}
                                                onChange={(e) => setNewAlert({ ...newAlert, return_date: e.target.value })}
                                                className="glass-input w-full"
                                            />
                                        </div>
                                    </div>

                                    <div className="grid grid-cols-2 gap-4">
                                        <div className="space-y-1">
                                            <label className="text-xs text-gray-400 uppercase">Precio Actual</label>
                                            <input
                                                type="number"
                                                value={newAlert.current_price}
                                                onChange={(e) => {
                                                    const price = parseFloat(e.target.value);
                                                    setNewAlert({
                                                        ...newAlert,
                                                        current_price: price,
                                                        target_price: Math.floor(price * 0.9)
                                                    });
                                                }}
                                                className="glass-input w-full"
                                                placeholder="5000"
                                            />
                                        </div>
                                        <div className="space-y-1">
                                            <label className="text-xs text-gray-400 uppercase">Avisar si baja a</label>
                                            <input
                                                type="number"
                                                value={newAlert.target_price}
                                                onChange={(e) => setNewAlert({ ...newAlert, target_price: parseFloat(e.target.value) })}
                                                className="glass-input w-full"
                                                placeholder="4500"
                                            />
                                        </div>
                                    </div>

                                    <div className="flex gap-3 pt-2">
                                        <button
                                            onClick={() => setShowCreateForm(false)}
                                            className="flex-1 px-4 py-2 rounded-xl text-sm hover:bg-white/5 transition-colors"
                                        >
                                            Cancelar
                                        </button>
                                        <button
                                            onClick={handleCreate}
                                            disabled={creating || !newAlert.origin || !newAlert.destination || !newAlert.departure_date}
                                            className="flex-1 px-4 py-2 bg-orange-500 hover:bg-orange-600 disabled:opacity-50 text-white rounded-xl text-sm font-bold transition-colors"
                                        >
                                            {creating ? 'Creando...' : 'Crear Alerta'}
                                        </button>
                                    </div>
                                </div>
                            )}

                            {/* Alerts List */}
                            {alerts.length === 0 && !showCreateForm ? (
                                <div className="text-center py-12">
                                    <BellOff className="mx-auto text-gray-600 mb-4" size={48} />
                                    <p className="text-gray-400">No tienes alertas de precio</p>
                                    <p className="text-sm text-gray-500 mt-2">
                                        Te avisaremos cuando bajen los precios
                                    </p>
                                </div>
                            ) : (
                                <div className="space-y-3">
                                    {alerts.map((alert) => (
                                        <div
                                            key={alert.id}
                                            className={`rounded-xl p-4 border transition-colors ${
                                                alert.is_active
                                                    ? 'bg-white/5 border-orange-500/30 hover:bg-white/10'
                                                    : 'bg-white/5 border-white/10 opacity-50'
                                            }`}
                                        >
                                            <div className="flex items-center justify-between">
                                                <div className="flex items-center gap-4">
                                                    <div className="w-12 h-12 rounded-full bg-orange-500/20 flex items-center justify-center">
                                                        <Plane className="text-orange-400" size={24} />
                                                    </div>
                                                    <div>
                                                        <p className="font-bold text-white text-lg">
                                                            {alert.origin} → {alert.destination}
                                                        </p>
                                                        <p className="text-sm text-gray-400">
                                                            {formatDate(alert.departure_date)}
                                                            {alert.return_date && ` - ${formatDate(alert.return_date)}`}
                                                        </p>
                                                    </div>
                                                </div>

                                                <div className="flex items-center gap-4">
                                                    <div className="text-right">
                                                        <div className="flex items-center gap-2">
                                                            <span className="text-gray-400 text-sm">Meta:</span>
                                                            <span className="text-orange-400 font-bold">
                                                                ${alert.target_price.toLocaleString()}
                                                            </span>
                                                        </div>
                                                        <div className="flex items-center gap-2">
                                                            <span className="text-gray-400 text-sm">Actual:</span>
                                                            <span className="text-white font-medium">
                                                                ${alert.current_price.toLocaleString()}
                                                            </span>
                                                        </div>
                                                        {alert.lowest_price < alert.current_price && (
                                                            <p className="text-xs text-green-400">
                                                                Más bajo: ${alert.lowest_price.toLocaleString()}
                                                            </p>
                                                        )}
                                                    </div>

                                                    <button
                                                        onClick={() => handleDelete(alert.id)}
                                                        className="p-2 hover:bg-red-500/20 rounded-lg text-red-400 transition-colors"
                                                    >
                                                        <Trash2 size={18} />
                                                    </button>
                                                </div>
                                            </div>

                                            {alert.notification_count > 0 && (
                                                <div className="mt-3 pt-3 border-t border-white/10">
                                                    <p className="text-xs text-gray-400">
                                                        {alert.notification_count} notificación{alert.notification_count !== 1 ? 'es' : ''} enviada{alert.notification_count !== 1 ? 's' : ''}
                                                    </p>
                                                </div>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            )}

                            {/* Add Button */}
                            {!showCreateForm && (
                                <button
                                    onClick={() => setShowCreateForm(true)}
                                    className="w-full mt-4 py-3 border-2 border-dashed border-white/20 rounded-xl text-gray-400 hover:border-orange-500/50 hover:text-orange-400 transition-colors flex items-center justify-center gap-2"
                                >
                                    <Plus size={20} />
                                    Crear Nueva Alerta
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
                            Revisamos los precios cada 6 horas y te notificamos por WhatsApp cuando el precio baje a tu meta.
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
};
