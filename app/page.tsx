import Link from "next/link";

export default function Home() {
  return (
    <main className="home">
      <section className="hero">
        <div className="brand-mark">C</div>
        <h1>Classio</h1>
        <p>La gestion scolaire simple, rapide et sécurisée.</p>
      </section>
      <section className="choices">
        <Link className="choice" href="/dashboard/superadmin/login"><b>Super-Admin</b><span>Gérer les écoles Classio</span></Link>
        <Link className="choice" href="/dashboard/ecole"><b>École</b><span>Accès du directeur</span></Link>
        <Link className="choice" href="/parent"><b>Parent</b><span>Suivre un élève</span></Link>
      </section>
      <Link className="test-link" href="/test">Tester Classio</Link>
    </main>
  );
}
