import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { App } from './App';
import { DatosProvider } from './data/DatosContext';
import './estilos.css';

const contenedor = document.getElementById('root');
if (!contenedor) {
  throw new Error('No se encontró el elemento raíz');
}

createRoot(contenedor).render(
  <StrictMode>
    <BrowserRouter>
      <DatosProvider>
        <App />
      </DatosProvider>
    </BrowserRouter>
  </StrictMode>,
);
