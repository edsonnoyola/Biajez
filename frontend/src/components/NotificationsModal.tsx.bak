import React, { useState, useEffect } from 'react';
import { X, Bell, Check, AlertCircle, Info } from 'lucide-react';
import axios from 'axios';
import { FlightChangeModal } from './FlightChangeModal';

interface Notification {
    id: string;
    type: string;
    title: string;
    message: string;
    read: boolean;
    action_required: boolean;
    related_order_id: string | null;
    created_at: string;
}

interface NotificationsModalProps {
    isOpen: boolean;
    onClose: () => void;
    userId: string;
}

export const NotificationsModal: React.FC<NotificationsModalProps> = ({ isOpen, onClose, userId }) => {
    const [notifications, setNotifications] = useState<Notification[]>([]);
    const [loading, setLoading] = useState(false);
    const [showRead, setShowRead] = useState(false);
    const [selectedChangeNotification, setSelectedChangeNotification] = useState<string | null>(null);

    useEffect(() => {
        if (isOpen) {
            fetchNotifications();
        }
    }, [isOpen, showRead]);

    const fetchNotifications = async () => {
        setLoading(true);
        try {
            const response = await axios.get(
                `http://localhost:8000/notifications/${userId}?include_read=${showRead}`
            );
            setNotifications(response.data.notifications || []);
        } catch (error) {
            console.error('Error fetching notifications:', error);
        } finally {
            setLoading(false);
        }
    };

    const markAsRead = async (notificationId: string) => {
        try {
            await axios.post(`http://localhost:8000/notifications/${notificationId}/mark-read`);
            // Update local state
            setNotifications(notifications.map(n =>
                n.id === notificationId ? { ...n, read: true, action_required: false } : n
            ));
        } catch (error) {
            console.error('Error marking notification as read:', error);
        }
    };

    const handleNotificationClick = (notification: Notification) => {
        if (notification.type === 'flight_change' && notification.action_required) {
            // Open FlightChangeModal
            setSelectedChangeNotification(notification.id);
        } else {
            // Just mark as read
            markAsRead(notification.id);
        }
    };

    const getIcon = (type: string) => {
        switch (type) {
            case 'flight_change':
                return <AlertCircle className="text-amber-400" size={20} />;
            case 'cancellation':
                return <AlertCircle className="text-red-400" size={20} />;
            case 'order_changed':
                return <Check className="text-green-400" size={20} />;
            default:
                return <Info className="text-blue-400" size={20} />;
        }
    };

    const formatDate = (dateString: string) => {
        const date = new Date(dateString);
        const now = new Date();
        const diffMs = now.getTime() - date.getTime();
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);

        if (diffMins < 1) return 'Just now';
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        if (diffDays < 7) return `${diffDays}d ago`;
        return date.toLocaleDateString();
    };

    if (!isOpen) return null;

    const unreadNotifications = notifications.filter(n => !n.read);
    const readNotifications = notifications.filter(n => n.read);

    return (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
            <div className="bg-gradient-to-br from-gray-900 to-gray-800 rounded-2xl shadow-2xl max-w-2xl w-full max-h-[80vh] overflow-hidden border border-white/10">
                {/* Header */}
                <div className="bg-gradient-to-r from-primary/20 to-accent/20 p-6 border-b border-white/10">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-primary/20 rounded-xl">
                                <Bell className="text-primary" size={24} />
                            </div>
                            <div>
                                <h2 className="text-2xl font-bold text-white">Notifications</h2>
                                <p className="text-sm text-gray-400">
                                    {unreadNotifications.length} unread
                                </p>
                            </div>
                        </div>
                        <button
                            onClick={onClose}
                            className="p-2 hover:bg-white/10 rounded-xl transition-colors"
                        >
                            <X className="text-gray-400" size={24} />
                        </button>
                    </div>

                    {/* Toggle */}
                    <div className="mt-4 flex items-center gap-2">
                        <input
                            type="checkbox"
                            id="showRead"
                            checked={showRead}
                            onChange={(e) => setShowRead(e.target.checked)}
                            className="w-4 h-4 rounded border-gray-600 bg-gray-800 text-primary focus:ring-primary"
                        />
                        <label htmlFor="showRead" className="text-sm text-gray-300 cursor-pointer">
                            Show read notifications
                        </label>
                    </div>
                </div>

                {/* Content */}
                <div className="p-6 overflow-y-auto max-h-[calc(80vh-180px)]">
                    {loading ? (
                        <div className="flex items-center justify-center py-12">
                            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
                        </div>
                    ) : notifications.length === 0 ? (
                        <div className="text-center py-12">
                            <Bell className="mx-auto text-gray-600 mb-4" size={48} />
                            <p className="text-gray-400 text-lg">No notifications</p>
                            <p className="text-gray-500 text-sm mt-2">
                                You're all caught up!
                            </p>
                        </div>
                    ) : (
                        <div className="space-y-3">
                            {/* Unread Notifications */}
                            {unreadNotifications.length > 0 && (
                                <>
                                    <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">
                                        Unread
                                    </h3>
                                    {unreadNotifications.map((notification) => (
                                        <div
                                            key={notification.id}
                                            className="bg-primary/10 border border-primary/30 rounded-xl p-4 hover:bg-primary/15 transition-all cursor-pointer"
                                            onClick={() => handleNotificationClick(notification)}
                                        >
                                            <div className="flex items-start gap-3">
                                                {getIcon(notification.type)}
                                                <div className="flex-1">
                                                    <div className="flex items-start justify-between gap-2">
                                                        <h4 className="font-semibold text-white">
                                                            {notification.title}
                                                        </h4>
                                                        <span className="text-xs text-gray-400 whitespace-nowrap">
                                                            {formatDate(notification.created_at)}
                                                        </span>
                                                    </div>
                                                    <p className="text-sm text-gray-300 mt-1">
                                                        {notification.message}
                                                    </p>
                                                    {notification.action_required && (
                                                        <div className="mt-2">
                                                            <span className="inline-flex items-center gap-1 px-2 py-1 bg-amber-500/20 text-amber-400 text-xs rounded-lg">
                                                                <AlertCircle size={12} />
                                                                Action Required
                                                            </span>
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                </>
                            )}

                            {/* Read Notifications */}
                            {showRead && readNotifications.length > 0 && (
                                <>
                                    <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3 mt-6">
                                        Read
                                    </h3>
                                    {readNotifications.map((notification) => (
                                        <div
                                            key={notification.id}
                                            className="bg-white/5 border border-white/10 rounded-xl p-4 opacity-60"
                                        >
                                            <div className="flex items-start gap-3">
                                                {getIcon(notification.type)}
                                                <div className="flex-1">
                                                    <div className="flex items-start justify-between gap-2">
                                                        <h4 className="font-semibold text-white">
                                                            {notification.title}
                                                        </h4>
                                                        <span className="text-xs text-gray-400 whitespace-nowrap">
                                                            {formatDate(notification.created_at)}
                                                        </span>
                                                    </div>
                                                    <p className="text-sm text-gray-300 mt-1">
                                                        {notification.message}
                                                    </p>
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                </>
                            )}
                        </div>
                    )}
                </div>
            </div>

            {/* FlightChangeModal */}
            {selectedChangeNotification && (
                <FlightChangeModal
                    notificationId={selectedChangeNotification}
                    isOpen={!!selectedChangeNotification}
                    onClose={() => setSelectedChangeNotification(null)}
                    onActionComplete={() => {
                        setSelectedChangeNotification(null);
                        fetchNotifications(); // Refresh notifications
                    }}
                />
            )}
        </div>
    );
};
