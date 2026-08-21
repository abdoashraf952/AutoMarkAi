/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // The FastAPI backend serves base64 image data inline, so no remote image
  // optimization is required. Everything talks to the API over fetch/EventSource.
};

export default nextConfig;
