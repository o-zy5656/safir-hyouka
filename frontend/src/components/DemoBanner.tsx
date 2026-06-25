export function DemoBanner() {
  if (import.meta.env.VITE_DEMO_MODE !== "true") return null;

  return (
    <div className="demo-banner" role="status">
      デモ環境 — 架空のサンプルデータです。実在の個人情報・評価データは含みません。
    </div>
  );
}
