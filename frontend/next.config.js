/** @type {import('next').NextConfig} */
const backendBaseUrl = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

const nextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        // 브라우저에서는 항상 같은 출처의 `/api`만 호출하고, 실제 백엔드 주소는 여기서 치환한다.
        destination: `${backendBaseUrl}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
