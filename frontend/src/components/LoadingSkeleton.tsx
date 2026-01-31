import React from 'react';

interface LoadingSkeletonProps {
    type?: 'flight' | 'hotel' | 'card' | 'text';
    count?: number;
}

export const LoadingSkeleton: React.FC<LoadingSkeletonProps> = ({ type = 'card', count = 1 }) => {
    const skeletons = Array.from({ length: count }, (_, i) => i);

    if (type === 'flight') {
        return (
            <>
                {skeletons.map((i) => (
                    <div
                        key={i}
                        className="animate-pulse bg-gradient-to-br from-gray-900/95 to-gray-800/95 backdrop-blur-xl border border-white/10 rounded-2xl p-5 mb-4 max-w-2xl w-full"
                    >
                        {/* Header Skeleton */}
                        <div className="flex justify-between items-start mb-5">
                            <div className="flex items-center gap-3">
                                <div className="w-12 h-12 rounded-xl bg-gray-700/50" />
                                <div className="space-y-2">
                                    <div className="h-4 w-24 bg-gray-700/50 rounded" />
                                    <div className="h-3 w-16 bg-gray-700/30 rounded" />
                                </div>
                            </div>
                            <div className="space-y-2 text-right">
                                <div className="h-8 w-20 bg-gray-700/50 rounded" />
                                <div className="h-3 w-16 bg-gray-700/30 rounded ml-auto" />
                            </div>
                        </div>

                        {/* Timeline Skeleton */}
                        <div className="mb-5">
                            <div className="flex items-center justify-between">
                                <div className="space-y-2">
                                    <div className="h-8 w-16 bg-gray-700/50 rounded" />
                                    <div className="h-5 w-14 bg-gray-700/40 rounded" />
                                    <div className="h-3 w-20 bg-gray-700/30 rounded" />
                                </div>
                                <div className="flex-[2] px-6 space-y-2">
                                    <div className="h-3 w-24 bg-gray-700/40 rounded mx-auto" />
                                    <div className="h-[2px] w-full bg-gray-700/30" />
                                    <div className="h-3 w-16 bg-gray-700/30 rounded mx-auto" />
                                </div>
                                <div className="space-y-2 text-right">
                                    <div className="h-8 w-16 bg-gray-700/50 rounded ml-auto" />
                                    <div className="h-5 w-14 bg-gray-700/40 rounded ml-auto" />
                                    <div className="h-3 w-20 bg-gray-700/30 rounded ml-auto" />
                                </div>
                            </div>
                        </div>

                        {/* Footer Skeleton */}
                        <div className="flex items-center justify-between pt-4 border-t border-white/10">
                            <div className="flex gap-2">
                                <div className="h-7 w-24 bg-gray-700/40 rounded-lg" />
                                <div className="h-7 w-16 bg-gray-700/40 rounded-lg" />
                            </div>
                            <div className="h-10 w-32 bg-gray-700/50 rounded-xl" />
                        </div>
                    </div>
                ))}
            </>
        );
    }

    if (type === 'hotel') {
        return (
            <>
                {skeletons.map((i) => (
                    <div
                        key={i}
                        className="animate-pulse bg-gradient-to-br from-gray-900/95 to-gray-800/95 backdrop-blur-xl border border-white/10 rounded-2xl overflow-hidden max-w-md w-full mb-4"
                    >
                        {/* Image Skeleton */}
                        <div className="h-48 bg-gray-700/50" />

                        {/* Content Skeleton */}
                        <div className="p-4 space-y-3">
                            <div className="space-y-2">
                                <div className="h-5 w-3/4 bg-gray-700/50 rounded" />
                                <div className="h-3 w-1/2 bg-gray-700/30 rounded" />
                            </div>

                            <div className="flex gap-2">
                                <div className="h-6 w-20 bg-gray-700/40 rounded-md" />
                                <div className="h-6 w-20 bg-gray-700/40 rounded-md" />
                                <div className="h-6 w-16 bg-gray-700/40 rounded-md" />
                            </div>

                            <div className="flex items-end justify-between pt-3 border-t border-white/10">
                                <div className="space-y-1">
                                    <div className="h-3 w-12 bg-gray-700/30 rounded" />
                                    <div className="h-7 w-20 bg-gray-700/50 rounded" />
                                    <div className="h-2 w-16 bg-gray-700/30 rounded" />
                                </div>
                                <div className="h-10 w-36 bg-gray-700/50 rounded-xl" />
                            </div>
                        </div>
                    </div>
                ))}
            </>
        );
    }

    if (type === 'text') {
        return (
            <>
                {skeletons.map((i) => (
                    <div key={i} className="animate-pulse space-y-2 mb-4">
                        <div className="h-4 bg-gray-700/50 rounded w-full" />
                        <div className="h-4 bg-gray-700/50 rounded w-5/6" />
                        <div className="h-4 bg-gray-700/50 rounded w-4/6" />
                    </div>
                ))}
            </>
        );
    }

    // Default card skeleton
    return (
        <>
            {skeletons.map((i) => (
                <div
                    key={i}
                    className="animate-pulse bg-gray-900/50 border border-white/10 rounded-2xl p-4 mb-4 w-full"
                >
                    <div className="space-y-3">
                        <div className="h-4 bg-gray-700/50 rounded w-3/4" />
                        <div className="h-4 bg-gray-700/50 rounded w-1/2" />
                        <div className="h-4 bg-gray-700/50 rounded w-5/6" />
                    </div>
                </div>
            ))}
        </>
    );
};
