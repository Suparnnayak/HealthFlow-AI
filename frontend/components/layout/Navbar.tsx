"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { isAuthenticated, logout, getUser } from "@/lib/auth";
import Logo from "@/components/ui/Logo";

const AUTH_NAV_LINKS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/hospitals", label: "Hospitals" },
  { href: "/agent", label: "AI Agent" },
  { href: "/system", label: "System" },
];

const PUBLIC_NAV_LINKS = [
  { href: "/about", label: "About" },
  { href: "/contact", label: "Contact" },
];

export default function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const [scrolled, setScrolled] = useState(false);
  const [authed, setAuthed] = useState(false);
  const [user, setUser] = useState<{ email: string; name?: string; role?: string } | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    const a = isAuthenticated();
    setAuthed(a);
    if (a) setUser(getUser());
    else setUser(null);
  }, [pathname]);

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const handleLogout = () => {
    logout();
    router.push("/");
  };

  const initials = user?.name
    ? user.name.split(" ").map((w) => w[0]).join("").toUpperCase().slice(0, 2)
    : user?.email?.[0]?.toUpperCase() || "U";

  const activeLinks = authed ? AUTH_NAV_LINKS : PUBLIC_NAV_LINKS;

  return (
    <>
      <motion.header
        initial={{ y: -100 }}
        animate={{ y: 0 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
        className={`fixed top-0 inset-x-0 z-50 transition-all duration-300 ${
          scrolled
            ? "glass border-b border-white/5"
            : "bg-transparent"
        }`}
      >
        <nav className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          {/* Left: Logo */}
          <Logo size="sm" />

          {/* Center: Nav links (desktop) */}
          <div className="hidden lg:flex items-center gap-1">
            {activeLinks.map((link) => {
              const active = pathname === link.href;
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`relative px-3.5 py-2 text-sm font-medium rounded-lg transition-colors ${
                    active
                      ? "text-cyan"
                      : "text-slate-400 hover:text-slate-200 hover:bg-white/5"
                  }`}
                >
                  {link.label}
                  {active && (
                    <motion.div
                      layoutId="nav-indicator"
                      className="absolute inset-x-1 -bottom-[1px] h-0.5 bg-gradient-to-r from-cyan to-teal rounded-full"
                      transition={{ type: "spring", bounce: 0.15, duration: 0.5 }}
                    />
                  )}
                </Link>
              );
            })}
            {authed && (user as any)?.role === "admin" && (
              <Link
                href="/admin"
                className={`relative px-3.5 py-2 text-sm font-medium rounded-lg transition-colors ${
                  pathname === "/admin"
                    ? "text-amber-400 font-semibold"
                    : "text-amber-400/80 hover:text-amber-300 hover:bg-white/5"
                }`}
              >
                Admin Center
                {pathname === "/admin" && (
                  <motion.div
                    layoutId="nav-indicator"
                    className="absolute inset-x-1 -bottom-[1px] h-0.5 bg-amber-400 rounded-full"
                    transition={{ type: "spring", bounce: 0.15, duration: 0.5 }}
                  />
                )}
              </Link>
            )}
          </div>

          {/* Right: Auth */}
          <div className="hidden lg:flex items-center gap-3">
            {authed ? (
              <>
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-full bg-gradient-to-br from-cyan to-teal flex items-center justify-center text-navy text-xs font-bold">
                    {initials}
                  </div>
                  <span className="text-sm text-slate-400 max-w-[120px] truncate">
                    {user?.name || user?.email}
                  </span>
                </div>
                <button
                  onClick={handleLogout}
                  className="px-3 py-1.5 text-sm font-medium text-slate-400 hover:text-white transition-colors"
                >
                  Logout
                </button>
              </>
            ) : (
              <>
                <Link
                  href="/login"
                  className="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white transition-colors"
                >
                  Sign In
                </Link>
                <Link
                  href="/register"
                  className="btn-primary !py-2 !px-5 text-sm"
                >
                  Get Started
                </Link>
              </>
            )}
          </div>

          {/* Mobile menu button */}
          <button
            onClick={() => setMobileOpen(!mobileOpen)}
            className="lg:hidden p-2 text-slate-400 hover:text-white"
          >
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              {mobileOpen ? (
                <path d="M18 6L6 18M6 6l12 12" />
              ) : (
                <path d="M4 6h16M4 12h16M4 18h16" />
              )}
            </svg>
          </button>
        </nav>
      </motion.header>

      {/* Mobile menu */}
      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="fixed inset-x-0 top-16 z-40 glass border-b border-white/5 lg:hidden"
          >
            <div className="px-4 py-4 space-y-1">
              {activeLinks.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  onClick={() => setMobileOpen(false)}
                  className={`block px-4 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                    pathname === link.href
                      ? "text-cyan bg-cyan/5"
                      : "text-slate-400 hover:text-white hover:bg-white/5"
                  }`}
                >
                  {link.label}
                </Link>
              ))}
              {authed && (user as any)?.role === "admin" && (
                <Link
                  href="/admin"
                  onClick={() => setMobileOpen(false)}
                  className={`block px-4 py-2.5 rounded-lg text-sm font-semibold transition-colors ${
                    pathname === "/admin"
                      ? "text-amber-400 bg-amber-400/10"
                      : "text-amber-400/80 hover:text-amber-300 hover:bg-white/5"
                  }`}
                >
                  Admin Center
                </Link>
              )}
              <div className="pt-3 border-t border-white/5">
                {authed ? (
                  <button
                    onClick={() => { handleLogout(); setMobileOpen(false); }}
                    className="w-full text-left px-4 py-2.5 rounded-lg text-sm text-slate-400 hover:text-white"
                  >
                    Logout
                  </button>
                ) : (
                  <div className="flex gap-2">
                    <Link href="/login" onClick={() => setMobileOpen(false)} className="flex-1 text-center btn-secondary !py-2 text-sm">Sign In</Link>
                    <Link href="/register" onClick={() => setMobileOpen(false)} className="flex-1 text-center btn-primary !py-2 text-sm">Register</Link>
                  </div>
                )}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}

