"use client";

export default function ErrorPage({ reset }: { reset: () => void }) {
  return (
    <main className="mx-auto max-w-xl px-5 py-20 text-center">
      <h1 className="text-3xl font-bold text-brand">Une erreur est survenue</h1>
      <p className="mt-3 text-slate-600">Veuillez réessayer ou revenir à l’accueil.</p>
      <button className="btn mt-6" type="button" onClick={() => reset()}>
        Réessayer
      </button>
    </main>
  );
}
