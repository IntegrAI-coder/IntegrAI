import { Navigate, NavLink, Route, Routes, Link } from 'react-router-dom';
import { Cursos } from './pages/Cursos';
import { Curso } from './pages/Curso';
import { Nino } from './pages/Nino';
import { Jardines } from './pages/Jardines';
import { Pendientes } from './pages/Pendientes';

export function App() {
  return (
    <div className="app">
      <header className="cabecera">
        <div className="contenedor cabecera__marca">
          <h1>
            <Link to="/" style={{ color: 'inherit', textDecoration: 'none' }}>
              IntegrAI
            </Link>
          </h1>
          <p>Dashboard de apoyo pedagógico</p>
          <nav className="navegacion">
            <NavLink to="/" end>
              Cursos
            </NavLink>
            <NavLink to="/jardines">Jardines</NavLink>
            <NavLink to="/pendientes">Por verificar</NavLink>
          </nav>
        </div>
      </header>

      <main className="principal">
        <div className="contenedor">
          <Routes>
            <Route path="/" element={<Cursos />} />
            <Route path="/curso/:idJardin/:sala" element={<Curso />} />
            <Route path="/nino/:idNino" element={<Nino />} />
            <Route path="/jardines" element={<Jardines />} />
            <Route path="/pendientes" element={<Pendientes />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
      </main>

      <footer className="pie">
        <div className="contenedor">
          <p>
            Herramienta de apoyo pedagógico, no constituye diagnóstico clínico.
          </p>
        </div>
      </footer>
    </div>
  );
}
