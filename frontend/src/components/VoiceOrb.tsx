import React from 'react';
import { motion } from 'framer-motion';

export type OrbState = 'idle' | 'listening' | 'processing' | 'speaking';

interface VoiceOrbProps {
    state: OrbState;
}

export const VoiceOrb: React.FC<VoiceOrbProps> = ({ state }) => {
    const variants: any = {
        idle: {
            scale: 1,
            opacity: 0.5,
            background: "linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%)",
            boxShadow: "0 0 20px rgba(59, 130, 246, 0.3)",
            transition: { duration: 0.5 }
        },
        listening: {
            scale: [1, 1.2, 1],
            opacity: 0.8,
            background: "linear-gradient(135deg, #ef4444 0%, #f97316 100%)", // Red/Orange for recording
            boxShadow: "0 0 40px rgba(239, 68, 68, 0.5)",
            transition: {
                repeat: Infinity,
                duration: 1.5,
                ease: "easeInOut"
            }
        },
        processing: {
            scale: [1, 0.9, 1.1, 1],
            rotate: [0, 180, 360],
            opacity: 0.9,
            background: "linear-gradient(135deg, #10b981 0%, #3b82f6 100%)", // Green/Blue
            boxShadow: "0 0 30px rgba(16, 185, 129, 0.4)",
            transition: {
                repeat: Infinity,
                duration: 2,
                ease: "linear"
            }
        },
        speaking: {
            scale: [1, 1.1, 1, 1.2, 1], // Random-ish pulses
            opacity: 1,
            background: "linear-gradient(135deg, #8b5cf6 0%, #ec4899 100%)", // Purple/Pink
            boxShadow: "0 0 50px rgba(139, 92, 246, 0.6)",
            transition: {
                repeat: Infinity,
                duration: 0.8,
                ease: "easeInOut"
            }
        }
    };

    return (
        <div className="relative flex items-center justify-center w-64 h-64">
            {/* Outer Glow Rings */}
            {state === 'speaking' && (
                <motion.div
                    className="absolute w-full h-full rounded-full bg-accent/20 blur-xl"
                    animate={{ scale: [1, 1.5, 1], opacity: [0.3, 0.6, 0.3] }}
                    transition={{ repeat: Infinity, duration: 2 }}
                />
            )}

            {/* Core Orb */}
            <motion.div
                className="w-32 h-32 rounded-full"
                variants={variants}
                animate={state}
                initial="idle"
            />

            {/* Status Text */}
            <motion.p
                className="absolute -bottom-12 text-sm font-medium text-gray-400 tracking-widest uppercase"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                key={state}
            >
                {state}
            </motion.p>
        </div>
    );
};
