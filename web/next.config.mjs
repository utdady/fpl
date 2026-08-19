/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,

  /*
   * Every page except two is prerendered at build time. The live season renders on
   * demand, and it reads the manifest through a computed path, which output file
   * tracing cannot detect by static analysis. Naming it here keeps the file inside
   * the serverless bundle; without it those two routes throw ENOENT once deployed
   * even though they work under `next start`.
   */
  outputFileTracingIncludes: {
    "/squad/[season]/[gw]": ["./public/data/manifest.json"],
    "/lab/[season]": ["./public/data/manifest.json"],
  },
};

export default nextConfig;
