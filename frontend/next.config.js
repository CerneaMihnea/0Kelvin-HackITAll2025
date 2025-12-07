/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'www.emag.ro',
      },
      {
        protocol: 'https',
        hostname: '**.emag.ro',
      },
      {
        protocol: 'https',
        hostname: '**.cdn.emag.ro',
      },
    ],
  },
}

module.exports = nextConfig

