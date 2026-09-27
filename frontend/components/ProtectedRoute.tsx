"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { isAuthenticated, getUserRole } from "@/lib/auth";

interface Props {
  children: React.ReactNode;
  requiredRole?: "admin" | "hospital_staff";
}

export default function ProtectedRoute({ children, requiredRole }: Props) {
  const router = useRouter();
  const [authorized, setAuthorized] = useState(false);

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push("/login");
      return;
    }

    if (requiredRole) {
      const userRole = getUserRole();
      if (requiredRole === "admin" && userRole !== "admin") {
        router.push("/dashboard");
        return;
      }
    }

    setAuthorized(true);
  }, [router, requiredRole]);

  if (!authorized) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-navy">
        <div className="w-8 h-8 border-2 border-cyan border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return <>{children}</>;
}

