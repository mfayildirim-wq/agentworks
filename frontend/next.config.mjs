/** @type {import('next').NextConfig} */
const config = {
  output: "standalone",
  reactStrictMode: true,
  images: { remotePatterns: [{ hostname: "lh3.googleusercontent.com" }] },
  async rewrites() {
    const backend = process.env.BACKEND_URL ?? "http://localhost:8000";
    return [{ source: "/media/:path*", destination: `${backend}/media/:path*` }];
  }
};
export default config;
