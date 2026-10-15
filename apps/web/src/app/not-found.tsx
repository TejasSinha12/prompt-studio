import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex flex-col items-center gap-2 px-6 py-16 text-center">
      <p className="text-base font-semibold">Page not found</p>
      <Link href="/" className="text-xs text-accent hover:underline">Back to dashboard</Link>
    </div>
  );
}
