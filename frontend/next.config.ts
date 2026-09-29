import type { NextConfig } from 'next';
const nextConfig: NextConfig = { agentRules: false, images: { unoptimized: true }, allowedDevOrigins: ['terminal.local'] };
export default nextConfig;
