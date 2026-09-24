module.exports = {
  ci: {
    collect: {
      url: [
        "http://localhost:3000/sandbox",
        "http://localhost:3000/sandbox/demo",
        "http://localhost:3000/admin/billing",
        "http://localhost:3000/admin/brand",
        "http://localhost:3000/admin/system",
      ],
      numberOfRuns: 3,
      startServerCommand: "npm run start",
    },
    assert: {
      assertions: {
        "categories:performance": ["error", { minScore: 0.9 }],
        "categories:accessibility": ["error", { minScore: 0.95 }],
        "categories:best-practices": ["error", { minScore: 0.9 }],
        "categories:seo": ["error", { minScore: 0.9 }],
        // Prevent Cumulative Layout Shift regressions
        "cumulative-layout-shift": ["error", { maxNumericValue: 0.1 }],
        // Target sub-1.5s Largest Contentful Paint
        "largest-contentful-paint": ["error", { maxNumericValue: 2000 }],
      },
    },
    upload: {
      target: "temporary-public-storage",
    },
  },
};
