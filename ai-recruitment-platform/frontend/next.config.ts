import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  images: {
    domains: [
      "logo.clearbit.com",
      "avatars.githubusercontent.com",
      "lh3.googleusercontent.com",
      "ui-avatars.com",
      "images.unsplash.com",
      "cdn.brandfetch.io",
    ],
    remotePatterns: [
      {
        protocol: "https",
        hostname: "**.clearbit.com",
      },
      {
        protocol: "https",
        hostname: "**.brandfetch.io",
      },
    ],
  },
  async rewrites() {
    const backendUrl =
      process.env.BACKEND_GATEWAY_URL || "http://localhost:8000";
    return [
      {
        source: "/api/employers/:path*",
        destination: `${backendUrl}/api/employers/:path*`,
      },
      {
        source: "/api/candidates/:path*",
        destination: `${backendUrl}/api/candidates/:path*`,
      },
      {
        source: "/api/outreach/:path*",
        destination: `${backendUrl}/api/outreach/:path*`,
      },
      {
        source: "/api/crm/:path*",
        destination: `${backendUrl}/api/crm/:path*`,
      },
      {
        source: "/api/analytics/:path*",
        destination: `${backendUrl}/api/analytics/:path*`,
      },
      {
        source: "/api/recruiters/:path*",
        destination: `${backendUrl}/api/recruiters/:path*`,
      },
      {
        source: "/api/auth/:path*",
        destination: `${backendUrl}/api/auth/:path*`,
      },
    ];
  },
  async headers() {
    return [
      {
        source: "/api/:path*",
        headers: [
          { key: "Access-Control-Allow-Credentials", value: "true" },
          { key: "Access-Control-Allow-Origin", value: "*" },
          {
            key: "Access-Control-Allow-Methods",
            value: "GET,OPTIONS,PATCH,DELETE,POST,PUT",
          },
          {
            key: "Access-Control-Allow-Headers",
            value:
              "X-CSRF-Token, X-Requested-With, Accept, Accept-Version, Content-Length, Content-MD5, Content-Type, Date, X-Api-Version, Authorization",
          },
        ],
      },
    ];
  },
  env: {
    NEXT_PUBLIC_APP_NAME: process.env.NEXT_PUBLIC_APP_NAME || "RecruitAI",
    NEXT_PUBLIC_APP_VERSION: process.env.NEXT_PUBLIC_APP_VERSION || "1.0.0",
    NEXT_PUBLIC_API_BASE_URL:
      process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000",
  },
};

export default nextConfig;
