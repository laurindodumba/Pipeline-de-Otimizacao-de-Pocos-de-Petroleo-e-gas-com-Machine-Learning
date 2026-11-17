import { useState } from 'react'
import { Link, NavLink, Outlet } from 'react-router-dom'

function AppShell() {
  const [searchMessage, setSearchMessage] = useState('')

  function handleFieldSearch(event) {
    event.preventDefault()
    const formData = new FormData(event.currentTarget)
    const query = String(formData.get('field-search') || '').trim().toLocaleLowerCase()
    if (!query) {
      setSearchMessage('')
      return
    }

    const fields = [...document.querySelectorAll('.field')]
    const match = fields.find((field) =>
      field.textContent.toLocaleLowerCase().includes(query),
    )

    if (!match) {
      setSearchMessage('Nenhum campo encontrado nesta página.')
      return
    }

    const dialog = document.querySelector('.estimate-dialog')
    if (dialog && !dialog.open) {
      dialog.showModal()
    }
    window.requestAnimationFrame(() => {
      match.scrollIntoView({ behavior: 'smooth', block: 'center' })
      match.querySelector('input')?.focus({ preventScroll: true })
    })
    setSearchMessage('Campo localizado.')
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Link className="brand" to="/" aria-label="PetroAI, página inicial">
          <span className="brand__mark" aria-hidden="true">P</span>
          <span>
            <strong>PetroAI</strong>
            <small>WELL ANALYTICS</small>
          </span>
        </Link>

        <p className="sidebar__label">MENU</p>
        <nav className="sidebar__nav" aria-label="Navegação principal">
          <NavLink to="/" end className={({ isActive }) => `nav-link${isActive ? ' nav-link--active' : ''}`}>
            <span className="nav-link__icon" aria-hidden="true">▦</span>
            Dashboard
          </NavLink>
        </nav>

        <p className="sidebar__label sidebar__label--other">OUTROS</p>
        <nav className="sidebar__nav" aria-label="Outras páginas">
          <NavLink to="/about" className={({ isActive }) => `nav-link${isActive ? ' nav-link--active' : ''}`}>
            <span className="nav-link__icon" aria-hidden="true">◉</span>
            Sobre o modelo
          </NavLink>
        </nav>
      </aside>

      <div className="app-main">
        <header className="topbar">
          <div className="topbar__search-wrap">
            <form className="topbar-search" role="search" onSubmit={handleFieldSearch}>
              <span aria-hidden="true">⌕</span>
              <input
                type="search"
                name="field-search"
                placeholder="Buscar parâmetro (ex.: pressão)"
                aria-label="Buscar parâmetro do poço"
              />
            </form>
            <span className="topbar__search-message" aria-live="polite">
              {searchMessage}
            </span>
          </div>
          <div className="topbar__user">
            <span className="topbar__avatar" aria-hidden="true">OP</span>
            <span className="topbar__user-name">Operações</span>
            <span className="topbar__chevron" aria-hidden="true">⌄</span>
          </div>
        </header>
        <main className="page-content">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

export default AppShell
