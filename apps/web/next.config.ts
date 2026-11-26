import type { NextConfig } from "next";
const config: NextConfig = {
  logging: { incomingRequests: { ignore: [/^\/gmail\/callback/] } },
  poweredByHeader: false,
  agentRules: false,
  experimental: { cpus: 1, serverActions: { bodySizeLimit: "6mb" } },
};
export default config;
