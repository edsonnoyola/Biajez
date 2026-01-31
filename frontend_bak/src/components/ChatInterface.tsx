import React, { useState, useRef, useEffect } from 'react';
import { Mic, Send, Bot, User, Loader2 } from 'lucide-react';
import { cn } from '../lib/utils';
import axios from 'axios';

interface Message {
    role: 'user' | 'assistant' | 'tool';
    content: string;
    tool_calls?: any[];
}

export const ChatInterface: React.FC = () => {
    const [messages, setMessages] = useState<Message[]>([
        { role: 'assistant', content: "Hello! I'm Antigravity. Where would you like to go?" }
    ]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const scrollRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [messages]);

    const sendMessage = async () => {
        if (!input.trim()) return;

        const userMsg: Message = { role: 'user', content: input };
        setMessages(prev => [...prev, userMsg]);
        setInput('');
        setIsLoading(true);

        try {
            // Call Backend API
            const response = await axios.post('http://localhost:8000/v1/chat', {
                user_id: "demo-user", // Hardcoded for demo
                messages: [...messages, userMsg].map(m => ({ role: m.role, content: m.content }))
            });

            const data = response.data;

            // The backend returns the full conversation or just the new messages. 
            // Based on my implementation, it returns { response: "content", messages: [...] }
            // Let's just append the assistant response for simplicity or use the updated history.

            if (data.response) {
                setMessages(prev => [...prev, { role: 'assistant', content: data.response }]);
            }

        } catch (error) {
            console.error("Chat Error:", error);
            setMessages(prev => [...prev, { role: 'assistant', content: "Sorry, I encountered an error." }]);
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="glass-panel h-[600px] flex flex-col p-4 relative overflow-hidden">
            <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-primary to-transparent opacity-50" />

            <div className="flex-1 overflow-y-auto space-y-4 mb-4 pr-2" ref={scrollRef}>
                {messages.filter(m => m.role !== 'tool').map((msg, i) => (
                    <div key={i} className={cn(
                        "flex gap-3 max-w-[80%]",
                        msg.role === 'user' ? "ml-auto flex-row-reverse" : "mr-auto"
                    )}>
                        <div className={cn(
                            "w-8 h-8 rounded-full flex items-center justify-center shrink-0",
                            msg.role === 'user' ? "bg-primary text-primary-foreground" : "bg-secondary text-secondary-foreground"
                        )}>
                            {msg.role === 'user' ? <User size={16} /> : <Bot size={16} />}
                        </div>

                        <div className={cn(
                            "p-3 rounded-2xl text-sm",
                            msg.role === 'user'
                                ? "bg-primary/20 text-foreground rounded-tr-none"
                                : "bg-secondary/50 text-foreground rounded-tl-none"
                        )}>
                            {msg.content}
                        </div>
                    </div>
                ))}

                {isLoading && (
                    <div className="flex gap-3 mr-auto max-w-[80%]">
                        <div className="w-8 h-8 rounded-full bg-secondary flex items-center justify-center shrink-0">
                            <Bot size={16} />
                        </div>
                        <div className="bg-secondary/50 p-3 rounded-2xl rounded-tl-none flex items-center gap-2">
                            <Loader2 size={16} className="animate-spin" />
                            <span className="text-xs opacity-70">Processing...</span>
                        </div>
                    </div>
                )}
            </div>

            <div className="flex gap-2">
                <input
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
                    placeholder="Type or speak..."
                    className="glass-input flex-1"
                />
                <button
                    onClick={sendMessage}
                    disabled={isLoading}
                    className="glass-button bg-primary hover:bg-primary/90 text-white"
                >
                    <Send size={18} />
                </button>
                <button className="glass-button text-accent hover:bg-accent/20 border-accent/20">
                    <Mic size={18} />
                </button>
            </div>
        </div>
    );
};
