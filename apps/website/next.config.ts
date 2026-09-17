import type { NextConfig } from "next";
const config: NextConfig = {
  transpilePackages: ["gpu-postal"],
  async headers() {
    return [
      {
        source: "/model-int5.bin.br",
        headers: [
          { key: "Content-Encoding", value: "br" },
          { key: "Content-Type", value: "application/octet-stream" },
          { key: "Cache-Control", value: "public, max-age=3600" },
        ],
      },
    ];
  },
};
export default config;
