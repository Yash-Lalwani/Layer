import { create } from 'zustand';
type DemoState = { slide: number; paused: boolean; question: string; setSlide: (slide: number) => void; setPaused: (paused: boolean) => void; setQuestion: (question: string) => void };
export const useDemoStore = create<DemoState>(set => ({ slide: 0, paused: false, question: 'overview', setSlide: slide => set({ slide }), setPaused: paused => set({ paused }), setQuestion: question => set({ question }) }));
