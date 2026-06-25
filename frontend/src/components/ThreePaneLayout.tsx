import type { ReactNode } from "react";

interface Props {
  left: ReactNode;
  center: ReactNode;
  right: ReactNode;
}

export function ThreePaneLayout({ left, center, right }: Props) {
  return (
    <div className="workspace">
      <aside className="pane pane-left">{left}</aside>
      <main className="pane pane-center">{center}</main>
      <aside className="pane pane-right">{right}</aside>
    </div>
  );
}
