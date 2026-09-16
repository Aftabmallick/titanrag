"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { AuthCard } from "@/components/auth/AuthCard";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import { Mail, Lock, User, Building, AlertCircle } from "lucide-react";

export default function RegisterPage() {
  const router = useRouter();
  const { success, error: toastError } = useToast();

  const [fullName, setFullName] = useState("");
  const [tenantName, setTenantName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fullName || !tenantName || !email || !password) {
      setErrorMessage("Please complete all registration fields.");
      return;
    }

    if (password.length < 8) {
      setErrorMessage("Password must contain at least 8 characters.");
      return;
    }

    setLoading(true);
    setErrorMessage(null);
    try {
      const res = await api.register({
        email,
        password,
        full_name: fullName,
        tenant_name: tenantName,
      });
      localStorage.setItem("titan_token", res.access_token);
      success("Tenant Provisioned!", "Your enterprise workspace is ready.");
      router.push("/");
    } catch (err: any) {
      setErrorMessage(err.message || "Registration failed. Email may already be registered.");
      toastError("Registration Failed", err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthCard
      title="Create Enterprise Tenant"
      subtitle="Deploy an isolated RAG environment with dedicated row-level security"
      footerText="Already have an account?"
      footerLinkText="Sign In"
      footerLinkHref="/login"
    >
      <form onSubmit={handleSubmit} className="space-y-3.5">
        {errorMessage && (
          <div className="flex items-center gap-2.5 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{errorMessage}</span>
          </div>
        )}

        <Input
          label="Administrator Full Name"
          placeholder="Jane Doe"
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
          leftIcon={<User className="w-4 h-4" />}
          required
        />

        <Input
          label="Organization / Tenant Name"
          placeholder="Acme Corp"
          value={tenantName}
          onChange={(e) => setTenantName(e.target.value)}
          leftIcon={<Building className="w-4 h-4" />}
          required
        />

        <Input
          label="Work Email"
          type="email"
          placeholder="jane@acme.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          leftIcon={<Mail className="w-4 h-4" />}
          required
        />

        <Input
          label="Password (min. 8 characters)"
          type="password"
          placeholder="••••••••••••"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          leftIcon={<Lock className="w-4 h-4" />}
          required
        />

        <Button type="submit" variant="primary" className="w-full mt-2" loading={loading}>
          Create Tenant & Workspace
        </Button>
      </form>
    </AuthCard>
  );
}
