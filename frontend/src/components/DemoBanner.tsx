export function DemoBanner() {
  if (import.meta.env.VITE_DEMO_MODE !== "true") return null;

  return (
    <div className="demo-banner" role="status">
      デモ環境 — 架空のサンプルデータです。上部の「デモ役割」から管理者・本部・施設長・リーダー・一般に切り替えできます。実在の個人情報は含みません。
    </div>
  );
}
