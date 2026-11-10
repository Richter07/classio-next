import logo from "../shared/ui/logo.svg";

export function App() {
  return (
    <main style={{ display: "grid", placeItems: "center", minHeight: "100dvh", padding: 16 }}>
      <img src={logo} alt="Classio" width={200} height={65} />
    </main>
  );
}
