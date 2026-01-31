import React from 'react';
import { CheckCircle2, XCircle, Info, AlertTriangle, X } from 'lucide-react';

export type ToastType = 'success' | 'error' | 'info' | 'warning';

interface ToastProps {
    type: ToastType;
    title: string;
    message?: string;
    onClose: () => void;
}

const ICONS = {
    success: CheckCircle2,
    error: XCircle,
    info: Info,
    warning: AlertTriangle,
};

const COLORS = {
    success: 'from-green-500/20 to-emerald-500/20 border-green-500/50',
    error: 'from-red-500/20 to-rose-500/20 border-red-500/50',
    info: 'from-blue-500/20 to-cyan-500/20 border-blue-500/50',
    warning: 'from-yellow-500/20 to-amber-500/20 border-yellow-500/50',
};

const ICON_COLORS = {
    success: 'text-green-400',
    error: 'text-red-400',
    info: 'text-blue-400',
    warning: 'text-yellow-400',
};

export const Toast: React.FC<ToastProps> = ({ type, title, message, onClose }) => {
    const Icon = ICONS[type];

    return (
        <div
            className={`
                min-w-[300px] max-w-md
                bg-gradient-to-r ${COLORS[type]}
                backdrop-blur-xl
                border rounded-xl
                p-4
                shadow-2xl
                animate-slideIn
            `}
        >
            <div className="flex items-start gap-3">
                <Icon className={`flex-shrink-0 ${ICON_COLORS[type]}`} size={24} />

                <div className="flex-1 min-w-0">
                    <h4 className="font-bold text-white text-sm mb-0.5">
                        {title}
                    </h4>
                    {message && (
                        <p className="text-gray-300 text-xs leading-relaxed">
                            {message}
                        </p>
                    )}
                </div>

                <button
                    onClick={onClose}
                    className="flex-shrink-0 text-gray-400 hover:text-white transition-colors"
                >
                    <X size={18} />
                </button>
            </div>
        </div>
    );
};

interface ToastContainerProps {
    toasts: Array<{
        id: string;
        type: ToastType;
        title: string;
        message?: string;
    }>;
    onClose: (id: string) => void;
}

export const ToastContainer: React.FC<ToastContainerProps> = ({ toasts, onClose }) => {
    if (toasts.length === 0) return null;

    return (
        <div className="fixed top-4 right-4 z-[9999] space-y-3">
            {toasts.map((toast) => (
                <Toast
                    key={toast.id}
                    type={toast.type}
                    title={toast.title}
                    message={toast.message}
                    onClose={() => onClose(toast.id)}
                />
            ))}
        </div>
    );
};

// Hook for easy toast usage
export const useToast = () => {
    const [toasts, setToasts] = React.useState<Array<{
        id: string;
        type: ToastType;
        title: string;
        message?: string;
    }>>([]);

    const showToast = (type: ToastType, title: string, message?: string) => {
        const id = Math.random().toString(36).substr(2, 9);
        setToasts(prev => [...prev, { id, type, title, message }]);

        // Auto remove after 5 seconds
        setTimeout(() => {
            removeToast(id);
        }, 5000);
    };

    const removeToast = (id: string) => {
        setToasts(prev => prev.filter(t => t.id !== id));
    };

    return {
        toasts,
        showToast,
        removeToast,
        success: (title: string, message?: string) => showToast('success', title, message),
        error: (title: string, message?: string) => showToast('error', title, message),
        info: (title: string, message?: string) => showToast('info', title, message),
        warning: (title: string, message?: string) => showToast('warning', title, message),
    };
};
