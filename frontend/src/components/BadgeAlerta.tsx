export function BadgeAlerta({ activa }: { activa: boolean }) {
  if (!activa) {
    return <span aria-hidden="true">—</span>;
  }
  return <span className="badge-alerta">Alerta</span>;
}
