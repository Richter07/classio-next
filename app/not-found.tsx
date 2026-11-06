import Link from "next/link";

export default function NotFound() {
  return (
    <main className="mx-auto max-w-xl px-5 py-20 text-center">
      <h1 className="text-3xl font-bold text-brand">Page introuvable</h1>
      <Link className="btn mt-6" href="/">
        Retour à l’accueil
      </Link>
    </main>
  );
}
