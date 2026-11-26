import Link from "next/link";

export default function GmailComplete() {
  return (
    <main id="main-content" className="signin">
      <section className="panel login">
        <h1>Return to your Gmail workspace.</h1>
        <p>
          Review your account and authorized senders before starting a sync.
        </p>
        <Link className="primary" href="/workspace?view=gmail">
          Return to Gmail updates
        </Link>
      </section>
    </main>
  );
}
