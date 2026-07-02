import { useState, type ReactNode } from "react";

interface Props {
  left: ReactNode;
  center: ReactNode;
  right: ReactNode;
  leftLabel?: string;
  centerLabel?: string;
  rightLabel?: string;
}

type MobilePane = "left" | "center" | "right";

export function ThreePaneLayout({
  left,
  center,
  right,
  leftLabel = "一覧",
  centerLabel = "入力",
  rightLabel = "参照",
}: Props) {
  const [mobilePane, setMobilePane] = useState<MobilePane>("center");

  return (
    <div className="workspace-shell">
      <div className="workspace-mobile-tabs" role="tablist" aria-label="ワークスペース切替">
        <button
          type="button"
          role="tab"
          aria-selected={mobilePane === "left"}
          className={mobilePane === "left" ? "active" : ""}
          onClick={() => setMobilePane("left")}
        >
          {leftLabel}
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mobilePane === "center"}
          className={mobilePane === "center" ? "active" : ""}
          onClick={() => setMobilePane("center")}
        >
          {centerLabel}
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mobilePane === "right"}
          className={mobilePane === "right" ? "active" : ""}
          onClick={() => setMobilePane("right")}
        >
          {rightLabel}
        </button>
      </div>
      <div className="workspace">
        <aside className={`pane pane-left${mobilePane === "left" ? " pane-active-mobile" : ""}`}>{left}</aside>
        <main className={`pane pane-center${mobilePane === "center" ? " pane-active-mobile" : ""}`}>
          {center}
        </main>
        <aside className={`pane pane-right${mobilePane === "right" ? " pane-active-mobile" : ""}`}>
          {right}
        </aside>
      </div>
    </div>
  );
}
