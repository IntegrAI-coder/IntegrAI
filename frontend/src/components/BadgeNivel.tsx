export function BadgeNivel({ nivel }: { nivel: number | null }) {
  if (nivel === null) {
    return <span className="badge-nivel badge-nivel--vacio">—</span>;
  }
  return <span className="badge-nivel">{nivel}</span>;
}
