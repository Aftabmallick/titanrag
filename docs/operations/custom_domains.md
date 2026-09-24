# Operational Runbook: White-Label Custom Domain Setup

> **Component**: White-Label Multi-Tenant Custom Domains (Phase 10)  
> **Audience**: Platform Operations & Enterprise Customer Onboarding Engineers  

---

## 1. Overview
TitanRAG Enterprise allows tenants to map custom domains (e.g., `chat.clientcorp.com` or `ai.internal.bank.com`) to their dedicated white-label portal. Custom domains are authenticated via DNS CNAME and TXT challenge verification, isolated by RLS, and served with automatic SSL.

---

## 2. Customer Setup Workflow

### Step 1: Customer Creates DNS Records
The tenant administrator must configure two DNS records with their DNS registrar:

1. **CNAME Record**:
   - **Host / Name**: `chat` (or subdomain of choice)
   - **Target**: `cname.titanrag.ai`
   - **TTL**: 300 seconds

2. **TXT Verification Record**:
   - **Host / Name**: `_titan-verify.chat.clientcorp.com`
   - **Value**: `titan-verify-token-[HEX_GENERATED_TOKEN]`

---

### Step 2: Verification via Platform Admin or API
Once DNS records propagate (typically 1–15 minutes):

```bash
# Trigger DNS verification check
curl -X POST https://api.titanrag.ai/api/v1/admin/brand/domain/verify \
  -H "Authorization: Bearer $PLATFORM_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"custom_domain": "chat.clientcorp.com"}'
```

The endpoint checks DNS `TXT` records using `dnspython`. Upon match:
- Sets `tenant_brand_configs.domain_verified = true`
- Issues Let's Encrypt SSL certificate via cert-manager / Caddy
- Flushes the tenant brand cache in Redis (`SET tenant:domain:chat.clientcorp.com`)

---

## 3. Nginx / Edge Layer Architecture

When an end-user navigates to `https://chat.clientcorp.com`:
1. Nginx captures `$host` as `chat.clientcorp.com`.
2. Proxies the request to TitanRAG API and Next.js frontend with:
   ```http
   X-Tenant-Custom-Domain: chat.clientcorp.com
   ```
3. Backend middleware queries `tenant_brand_configs` where `custom_domain = $host`.
4. Tenant ID is bound to the PostgreSQL RLS session.
5. Frontend injects tenant branding CSS variables (`--brand-primary`, `--brand-logo-light`) into the document `<head>`.

---

## 4. Troubleshooting & On-Call FAQ

### Issue: Domain verification fails with "TXT record mismatch"
- **Diagnostic**: Run `dig +short TXT _titan-verify.chat.clientcorp.com`
- **Solution**: Confirm DNS propagation. If Cloudflare proxy ("Orange Cloud") is active on the CNAME, ensure the TXT verification record is not proxied.

### Issue: SSL handshake fails on custom domain
- **Diagnostic**: Run `openssl s_client -connect chat.clientcorp.com:443 -servername chat.clientcorp.com`
- **Solution**: Verify cert-manager certificate status with `kubectl get certificates -n titanrag-prod`.
