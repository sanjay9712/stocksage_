import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex min-h-[50vh] items-center justify-center p-6">
      <div className="text-center">
        <h1 className="text-2xl font-semibold text-slate-300">404</h1>
        <p className="text-sm text-slate-500 mt-2">This page doesn&apos;t exist.</p>
        <Link
          href="/"
          className="inline-block mt-4 rounded-md bg-slate-700 hover:bg-slate-600 px-4 py-2 text-sm"
        >
          Back to dashboard
        </Link>
      </div>
    </div>
  );
}
