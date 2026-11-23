import { Brand } from "../../components/identity";
export default function Loading() {
  return (
    <main id="main-content" className="loading-page">
      <Brand />
      <section aria-busy="true" role="status">
        <h1>Opening workspace…</h1>
        <div className="skeleton" />
        <div className="skeleton short" />
      </section>
    </main>
  );
}
