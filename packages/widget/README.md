# @titanrag/widget

Zero-dependency, Shadow DOM-isolated, embeddable chat widget for the [TitanRAG Enterprise Platform](https://github.com/Aftabmallick/titanrag).

[![npm](https://img.shields.io/npm/v/@titanrag/widget.svg)](https://www.npmjs.com/package/@titanrag/widget)
[![License: BSL-1.1](https://img.shields.io/badge/License-BSL--1.1-orange.svg)](https://github.com/Aftabmallick/titanrag/blob/master/LICENSE)
[![Bundle Size](https://img.shields.io/badge/bundle-~17KB%20(5.7KB%20gz)-success.svg)](https://www.npmjs.com/package/@titanrag/widget)

---

## Features

- ⚡ **Zero Dependencies**: Lightweight standalone bundle (< 6KB gzipped).
- 🛡️ **Shadow DOM Encapsulation**: Complete CSS isolation — guaranteed zero style bleeding into your host website or app.
- 🌊 **Real-Time Streaming**: Token-by-token SSE streaming with low latency.
- 📚 **Interactive Citations**: Hoverable source citations, page numbers, and snippet previews.
- 🎨 **Themeable**: Built-in support for `light`, `dark`, and `auto` (system `prefers-color-scheme`), with customizable accent colors.
- 📱 **Responsive**: Works on desktop, mobile drawer, or embedded `inline` mode.

---

## Installation

### Via npm / yarn / pnpm

```bash
npm install @titanrag/widget
```

```bash
yarn add @titanrag/widget
```

```bash
pnpm add @titanrag/widget
```

### Via CDN (Script Tag)

Add the script directly before the closing `</body>` tag:

```html
<script src="https://cdn.jsdelivr.net/npm/@titanrag/widget@0.1.1/dist/widget.js" async></script>
```

---

## Quickstart

### 1. HTML / Static Site

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>My Website</title>
</head>
<body>
  <!-- Drop the custom element anywhere in your page -->
  <titan-chat
    workspace="your-workspace-id"
    api-key="your_api_key"
    base-url="https://api.titanrag.com"
    theme="auto"
    position="bottom-right"
    accent-color="#6366F1"
    bot-name="Titan Assistant"
    greeting-message="Hi! How can I help you today?"
    placeholder="Ask anything about our documentation..."
  ></titan-chat>

  <script src="https://cdn.jsdelivr.net/npm/@titanrag/widget@0.1.1/dist/widget.js" async></script>
</body>
</html>
```

### 2. Next.js / React

Import the package once in your layout or client component:

```tsx
'use client';

import { useEffect } from 'react';

export default function ChatWidget() {
  useEffect(() => {
    // Dynamic import to ensure browser execution
    import('@titanrag/widget');
  }, []);

  return (
    // @ts-ignore - custom element
    <titan-chat
      workspace={process.env.NEXT_PUBLIC_TITAN_WORKSPACE!}
      api-key={process.env.NEXT_PUBLIC_TITAN_API_KEY!}
      base-url={process.env.NEXT_PUBLIC_TITAN_API_URL || 'https://api.titanrag.com'}
      theme="auto"
      position="bottom-right"
      accent-color="#6366F1"
      bot-name="Support AI"
    />
  );
}
```

### 3. Vue 3

```vue
<template>
  <titan-chat
    workspace="your-workspace-id"
    api-key="your_api_key"
    base-url="https://api.titanrag.com"
    theme="auto"
    position="bottom-right"
  />
</template>

<script setup>
import { onMounted } from 'vue';

onMounted(async () => {
  await import('@titanrag/widget');
});
</script>
```

---

## Configuration Attributes

| Attribute | Type | Default | Description |
|:---|:---|:---|:---|
| `workspace` | `string` | *(Required)* | Target workspace ID or slug in TitanRAG. |
| `api-key` | `string` | *(Required)* | Workspace API key with chat permissions. |
| `base-url` | `string` | *(Required)* | API base URL (e.g. `https://api.titanrag.com` or `http://localhost:8000`). |
| `theme` | `"light" \| "dark" \| "auto"` | `"auto"` | Color theme. `"auto"` matches device OS theme. |
| `position` | `"bottom-right" \| "bottom-left" \| "inline"` | `"bottom-right"` | Screen launcher placement or embedded document mode. |
| `accent-color` | `string` (hex) | `"#6366F1"` | Primary brand highlight color. |
| `bot-name` | `string` | `"Titan Assistant"` | Header title shown at top of the chat window. |
| `greeting-message`| `string` | `"Hello! How can I help..."` | Initial welcoming message shown before user inputs query. |
| `placeholder` | `string` | `"Ask a question..."` | Placeholder text in the message input field. |

---

## License

TitanRAG is licensed under the [Business Source License 1.1 (BSL-1.1)](https://github.com/Aftabmallick/titanrag/blob/master/LICENSE).
