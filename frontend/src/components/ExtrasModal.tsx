import React, { useState, useEffect } from 'react';
import { X, UtensilsCrossed, Wifi, Armchair, Luggage, Check, ShoppingCart, AlertCircle } from 'lucide-react';
import axios from 'axios';
import API_URL from '../config/api';

interface Service {
    id: string;
    type: string;
    price: string;
    currency: string;
    description: string;
    segment_id: string;
    meal_type?: string;
    weight?: number;
}

interface AvailableServices {
    meals: Service[];
    bags: Service[];
    seats: Service[];
    other: Service[];
}

interface ExtrasModalProps {
    isOpen: boolean;
    onClose: () => void;
    offerId?: string;
    orderId?: string;
    onServicesAdded?: () => void;
}

const MEAL_NAMES: { [key: string]: string } = {
    'STANDARD': 'Comida Estándar',
    'VEGETARIAN': 'Vegetariano',
    'VEGAN': 'Vegano',
    'KOSHER': 'Kosher',
    'HALAL': 'Halal',
    'GLUTEN_FREE': 'Sin Gluten',
    'CHILD': 'Menú Infantil',
    'DIABETIC': 'Diabético',
};

export const ExtrasModal: React.FC<ExtrasModalProps> = ({
    isOpen,
    onClose,
    offerId,
    orderId,
    onServicesAdded
}) => {
    const [services, setServices] = useState<AvailableServices | null>(null);
    const [loading, setLoading] = useState(false);
    const [selectedServices, setSelectedServices] = useState<Set<string>>(new Set());
    const [adding, setAdding] = useState(false);
    const [activeTab, setActiveTab] = useState<'meals' | 'bags' | 'seats' | 'other'>('meals');

    useEffect(() => {
        if (isOpen && offerId) {
            fetchServices();
        }
    }, [isOpen, offerId]);

    const fetchServices = async () => {
        if (!offerId) return;

        setLoading(true);
        try {
            const response = await axios.get(`${API_URL}/api/ancillary/available/${offerId}`);
            setServices(response.data);
        } catch (error) {
            console.error('Error fetching services:', error);
        } finally {
            setLoading(false);
        }
    };

    const toggleService = (serviceId: string) => {
        const newSelected = new Set(selectedServices);
        if (newSelected.has(serviceId)) {
            newSelected.delete(serviceId);
        } else {
            newSelected.add(serviceId);
        }
        setSelectedServices(newSelected);
    };

    const handleAddServices = async () => {
        if (!orderId || selectedServices.size === 0) return;

        setAdding(true);
        try {
            await axios.post(`${API_URL}/api/ancillary/add`, {
                order_id: orderId,
                service_ids: Array.from(selectedServices)
            });
            alert('Servicios agregados correctamente');
            onServicesAdded?.();
            onClose();
        } catch (error) {
            console.error('Error adding services:', error);
            alert('Error al agregar servicios');
        } finally {
            setAdding(false);
        }
    };

    const getTotal = () => {
        if (!services) return 0;
        let total = 0;
        const allServices = [...services.meals, ...services.bags, ...services.seats, ...services.other];
        allServices.forEach(s => {
            if (selectedServices.has(s.id)) {
                total += parseFloat(s.price);
            }
        });
        return total;
    };

    const tabs = [
        { key: 'meals', label: 'Comidas', icon: UtensilsCrossed, count: services?.meals.length || 0 },
        { key: 'bags', label: 'Equipaje', icon: Luggage, count: services?.bags.length || 0 },
        { key: 'seats', label: 'Asientos', icon: Armchair, count: services?.seats.length || 0 },
        { key: 'other', label: 'Otros', icon: Wifi, count: services?.other.length || 0 },
    ];

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
            <div className="bg-gray-900/95 backdrop-blur-xl border border-white/10 w-full max-w-3xl rounded-3xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200 flex flex-col max-h-[90vh]">

                {/* Header */}
                <div className="bg-gradient-to-r from-blue-900 to-gray-900 p-6 text-white relative flex items-center justify-between border-b border-white/5">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-blue-500/20 flex items-center justify-center text-blue-400">
                            <ShoppingCart size={20} />
                        </div>
                        <div>
                            <h2 className="text-xl font-bold">Servicios Adicionales</h2>
                            <p className="text-sm text-gray-400">
                                Personaliza tu viaje con extras
                            </p>
                        </div>
                    </div>
                    <button onClick={onClose} className="p-2 hover:bg-white/10 rounded-full transition-colors">
                        <X size={20} />
                    </button>
                </div>

                {/* Tabs */}
                <div className="flex border-b border-white/5">
                    {tabs.map((tab) => (
                        <button
                            key={tab.key}
                            onClick={() => setActiveTab(tab.key as any)}
                            className={`flex-1 py-3 px-4 flex items-center justify-center gap-2 text-sm font-medium transition-colors ${
                                activeTab === tab.key
                                    ? 'text-blue-400 border-b-2 border-blue-400 bg-blue-500/10'
                                    : 'text-gray-400 hover:text-white hover:bg-white/5'
                            }`}
                        >
                            <tab.icon size={16} />
                            {tab.label}
                            {tab.count > 0 && (
                                <span className="ml-1 px-1.5 py-0.5 bg-white/10 rounded text-xs">
                                    {tab.count}
                                </span>
                            )}
                        </button>
                    ))}
                </div>

                {/* Content */}
                <div className="p-6 overflow-y-auto custom-scrollbar flex-1">
                    {loading ? (
                        <div className="text-center py-8">
                            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto"></div>
                            <p className="text-gray-400 mt-2">Cargando servicios...</p>
                        </div>
                    ) : !services ? (
                        <div className="text-center py-12">
                            <AlertCircle className="mx-auto text-gray-600 mb-4" size={48} />
                            <p className="text-gray-400">No se pudieron cargar los servicios</p>
                        </div>
                    ) : (
                        <div className="space-y-3">
                            {/* Meals Tab */}
                            {activeTab === 'meals' && (
                                services.meals.length === 0 ? (
                                    <div className="text-center py-8 text-gray-400">
                                        <UtensilsCrossed className="mx-auto mb-2" size={32} />
                                        <p>No hay opciones de comida disponibles</p>
                                    </div>
                                ) : (
                                    services.meals.map((meal) => (
                                        <ServiceCard
                                            key={meal.id}
                                            service={meal}
                                            label={MEAL_NAMES[meal.meal_type || ''] || meal.meal_type || 'Comida'}
                                            icon={<UtensilsCrossed size={20} />}
                                            selected={selectedServices.has(meal.id)}
                                            onToggle={() => toggleService(meal.id)}
                                        />
                                    ))
                                )
                            )}

                            {/* Bags Tab */}
                            {activeTab === 'bags' && (
                                services.bags.length === 0 ? (
                                    <div className="text-center py-8 text-gray-400">
                                        <Luggage className="mx-auto mb-2" size={32} />
                                        <p>No hay opciones de equipaje disponibles</p>
                                    </div>
                                ) : (
                                    services.bags.map((bag) => (
                                        <ServiceCard
                                            key={bag.id}
                                            service={bag}
                                            label={bag.weight ? `Maleta ${bag.weight}kg` : 'Equipaje Extra'}
                                            icon={<Luggage size={20} />}
                                            selected={selectedServices.has(bag.id)}
                                            onToggle={() => toggleService(bag.id)}
                                        />
                                    ))
                                )
                            )}

                            {/* Seats Tab */}
                            {activeTab === 'seats' && (
                                services.seats.length === 0 ? (
                                    <div className="text-center py-8 text-gray-400">
                                        <Armchair className="mx-auto mb-2" size={32} />
                                        <p>No hay opciones de asiento disponibles</p>
                                        <p className="text-sm mt-1">Usa el mapa de asientos para seleccionar</p>
                                    </div>
                                ) : (
                                    services.seats.map((seat) => (
                                        <ServiceCard
                                            key={seat.id}
                                            service={seat}
                                            label={seat.description || 'Selección de Asiento'}
                                            icon={<Armchair size={20} />}
                                            selected={selectedServices.has(seat.id)}
                                            onToggle={() => toggleService(seat.id)}
                                        />
                                    ))
                                )
                            )}

                            {/* Other Tab */}
                            {activeTab === 'other' && (
                                services.other.length === 0 ? (
                                    <div className="text-center py-8 text-gray-400">
                                        <Wifi className="mx-auto mb-2" size={32} />
                                        <p>No hay otros servicios disponibles</p>
                                    </div>
                                ) : (
                                    services.other.map((service) => (
                                        <ServiceCard
                                            key={service.id}
                                            service={service}
                                            label={service.description || service.type}
                                            icon={<Wifi size={20} />}
                                            selected={selectedServices.has(service.id)}
                                            onToggle={() => toggleService(service.id)}
                                        />
                                    ))
                                )
                            )}
                        </div>
                    )}
                </div>

                {/* Footer */}
                {selectedServices.size > 0 && (
                    <div className="p-4 border-t border-white/5 bg-gradient-to-r from-blue-900/50 to-gray-900/50">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-sm text-gray-400">
                                    {selectedServices.size} servicio{selectedServices.size !== 1 ? 's' : ''} seleccionado{selectedServices.size !== 1 ? 's' : ''}
                                </p>
                                <p className="text-2xl font-bold text-blue-400">
                                    +${getTotal().toFixed(2)} USD
                                </p>
                            </div>
                            <button
                                onClick={handleAddServices}
                                disabled={adding || !orderId}
                                className="px-6 py-3 bg-blue-500 hover:bg-blue-600 disabled:opacity-50 text-white rounded-xl font-bold transition-colors flex items-center gap-2"
                            >
                                {adding ? 'Agregando...' : (
                                    <>
                                        <Check size={18} />
                                        Agregar Servicios
                                    </>
                                )}
                            </button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

// Service Card Component
const ServiceCard: React.FC<{
    service: Service;
    label: string;
    icon: React.ReactNode;
    selected: boolean;
    onToggle: () => void;
}> = ({ service, label, icon, selected, onToggle }) => (
    <button
        onClick={onToggle}
        className={`w-full p-4 rounded-xl border transition-all text-left flex items-center gap-4 ${
            selected
                ? 'bg-blue-500/20 border-blue-500/50'
                : 'bg-white/5 border-white/10 hover:bg-white/10'
        }`}
    >
        <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
            selected ? 'bg-blue-500 text-white' : 'bg-white/10 text-gray-400'
        }`}>
            {selected ? <Check size={20} /> : icon}
        </div>
        <div className="flex-1">
            <p className="font-medium text-white">{label}</p>
            {service.description && (
                <p className="text-sm text-gray-400">{service.description}</p>
            )}
        </div>
        <div className="text-right">
            <p className={`font-bold ${selected ? 'text-blue-400' : 'text-white'}`}>
                ${service.price}
            </p>
            <p className="text-xs text-gray-500">{service.currency}</p>
        </div>
    </button>
);
