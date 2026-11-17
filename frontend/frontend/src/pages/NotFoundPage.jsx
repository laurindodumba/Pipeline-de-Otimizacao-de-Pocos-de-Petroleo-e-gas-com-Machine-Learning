import { Link } from 'react-router-dom'

function NotFoundPage() {
  return (
    <section className="simple-page">
      <p className="eyebrow">ERRO 404</p>
      <h1>Página não encontrada</h1>
      <p>O endereço acessado não corresponde a uma página deste sistema.</p>
      <Link className="text-link" to="/">Voltar à visão geral</Link>
    </section>
  )
}

export default NotFoundPage
