import { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  const baseUrl = process.env.NEXT_PUBLIC_APP_URL || "https://titanrag.ai";

  return {
    rules: [
      {
        userAgent: "*",
        allow: ["/", "/sandbox", "/sandbox/demo", "/docs"],
        disallow: ["/admin/", "/api/", "/dashboard/"],
      },
    ],
    sitemap: `${baseUrl}/sitemap.xml`,
  };
}
