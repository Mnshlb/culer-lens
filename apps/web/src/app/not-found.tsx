import Link from "next/link";

export default function NotFound() {
  return (
    <div className="grid min-h-[50vh] place-items-center text-center">
      <div>
        <p className="text-xs uppercase tracking-[0.14em] text-primary">404</p>
        <h1 className="mt-2 text-2xl font-semibold">Offside. That page does not exist.</h1>
        <Link href="/" className="mt-4 inline-block text-sm text-primary hover:underline">Back to the overview</Link>
      </div>
    </div>
  );
}
