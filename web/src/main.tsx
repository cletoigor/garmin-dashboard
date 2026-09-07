import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { HeroUIProvider } from '@heroui/react'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js'
import './index.css'
import App from './App.tsx'
import { ThemeProvider } from './theme'

// Registro global dos componentes do Chart.js (graficos chegam em uma proxima slice).
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler,
)

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider>
      <HeroUIProvider>
        <App />
      </HeroUIProvider>
    </ThemeProvider>
  </StrictMode>,
)
