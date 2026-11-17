import { useEffect, useRef, useState } from 'react'
import WellInputDialog from '../components/wells/WellInputDialog.jsx'
import { getDashboardSummary } from '../services/apiClient.js'
import './DashboardPage.css'

const moneyFormatter = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 2,
})

function MarginDistributionChart({ data }) {
  const maximumCount = Math.max(...data.map((band) => band.count), 1)

  return (
    <div
      className="bar-chart"
      role="img"
      aria-label="Distribuição do número de poços por faixa de margem líquida diária"
    >
      {data.map((band) => (
        <div className="bar-chart__column" key={band.label}>
          <span className="bar-chart__count">{band.count}</span>
          <div className="bar-chart__track">
            <span
              className="bar-chart__bar"
              style={{ height: `${Math.max((band.count / maximumCount) * 100, 2)}%` }}
            />
          </div>
          <span className="bar-chart__label">{band.label}</span>
        </div>
      ))}
    </div>
  )
}

function MarginStatusChart({ summary }) {
  const positivePercentage = summary.positive_margin_percentage
  const donutStyle = {
    background: `conic-gradient(#6574d8 0 ${positivePercentage}%, #f5ad69 ${positivePercentage}% 100%)`,
  }

  return (
    <div className="status-chart">
      <div
        className="status-chart__donut"
        style={donutStyle}
        role="img"
        aria-label={`${summary.positive_margin_count} poços com margem positiva e ${summary.negative_margin_count} com margem negativa`}
      >
        <div className="status-chart__center">
          <strong>{Math.round(positivePercentage)}%</strong>
          <span>positiva</span>
        </div>
      </div>
      <div className="status-chart__legend">
        <p>
          <span className="legend-dot legend-dot--positive" />
          <span>Margem positiva</span>
          <strong>{summary.positive_margin_count}</strong>
        </p>
        <p>
          <span className="legend-dot legend-dot--negative" />
          <span>Margem negativa</span>
          <strong>{summary.negative_margin_count}</strong>
        </p>
      </div>
    </div>
  )
}

function RevenueComponentsChart({ data }) {
  const maximumValue = Math.max(...data.map((item) => item.average_usd_per_well_day), 1)

  return (
    <div className="component-chart">
      {data.map((item) => (
        <div className="component-chart__row" key={item.label}>
          <div className="component-chart__heading">
            <span>{item.label}</span>
            <strong>{moneyFormatter.format(item.average_usd_per_well_day)}</strong>
          </div>
          <div className="component-chart__track">
            <span
              className={`component-chart__bar${item.label === 'OPEX' ? ' component-chart__bar--cost' : ''}`}
              style={{
                width: `${Math.max((item.average_usd_per_well_day / maximumValue) * 100, 1)}%`,
              }}
            />
          </div>
        </div>
      ))}
    </div>
  )
}

function DashboardPage() {
  const dialogRef = useRef(null)
  const [prediction, setPrediction] = useState(null)
  const [summary, setSummary] = useState(null)
  const [summaryError, setSummaryError] = useState('')

  useEffect(() => {
    let active = true

    getDashboardSummary()
      .then((data) => {
        if (active) {
          setSummary(data)
        }
      })
      .catch((error) => {
        if (active) {
          setSummaryError(error.message || 'Não foi possível carregar os dados do dashboard.')
        }
      })

    return () => {
      active = false
    }
  }, [])

  function openEstimateForm() {
    dialogRef.current?.showModal()
  }

  return (
    <div className="dashboard-page">
      <div className="dashboard-heading">
        <div>
          <h1>Dashboard</h1>
          <p>
            {summary
              ? `${summary.well_count} poços · margem líquida observada`
              : 'Resumo da análise de margem operacional dos poços.'}
          </p>
        </div>
        <button className="report-button" type="button" onClick={openEstimateForm}>
          Nova estimativa
        </button>
      </div>

      {summaryError && (
        <p className="dashboard-error" role="alert">
          Não foi possível carregar os gráficos: {summaryError}
        </p>
      )}

      {!summary && !summaryError && (
        <p className="dashboard-loading" role="status">Carregando dados dos poços…</p>
      )}

      {summary && (
        <>
          <section className="dashboard-top" aria-label="Distribuição das margens dos poços">
            <article className="dashboard-widget">
              <div className="widget-heading">
                <div>
                  <h2>Distribuição da margem diária</h2>
                  <p>
                    Média {moneyFormatter.format(summary.average_daily_net_margin_usd)} ·
                    mediana {moneyFormatter.format(summary.median_daily_net_margin_usd)}
                  </p>
                </div>
              </div>
              <MarginDistributionChart data={summary.margin_distribution} />
              <p className="chart-caption">
                Número de poços em cada faixa de margem líquida observada (USD/dia).
              </p>
            </article>

            <article className="dashboard-widget">
              <div className="widget-heading">
                <div>
                  <h2>Margem por poço</h2>
                  <p>Resultado líquido observado na base</p>
                </div>
              </div>
              <MarginStatusChart summary={summary} />
              <p className="chart-caption">
                {summary.positive_margin_percentage}% dos poços apresentam margem acima de zero.
              </p>
            </article>
          </section>

          <section className="dashboard-bottom" aria-label="Análises adicionais">
            <article className="bottom-widget">
              <h2>Receita e custo médios</h2>
              <p className="widget-subtitle">USD por poço, por dia</p>
              <RevenueComponentsChart data={summary.revenue_components} />
            </article>

            <article className="bottom-widget">
              <h2>Maiores margens observadas</h2>
              <p className="widget-subtitle">Poços com maior margem líquida diária</p>
              <ol className="top-wells">
                {summary.top_wells.map((well, index) => (
                  <li key={well.well_id}>
                    <span className="top-wells__rank">{String(index + 1).padStart(2, '0')}</span>
                    <span>Poço {well.well_id}</span>
                    <strong>{moneyFormatter.format(well.daily_net_margin_usd)}</strong>
                  </li>
                ))}
              </ol>
            </article>

            <article className="bottom-widget">
              <h2>Última estimativa</h2>
              <p className="widget-subtitle">Previsão para condições informadas</p>
              {prediction ? (
                <>
                  <p className="prediction-value">
                    {moneyFormatter.format(prediction.estimated_daily_net_margin_usd)}
                  </p>
                  <p className="prediction-model">Modelo: {prediction.model}</p>
                </>
              ) : (
                <div className="prediction-empty">
                  <p>Nenhuma estimativa gerada nesta sessão.</p>
                  <button className="text-button" type="button" onClick={openEstimateForm}>
                    Informar condições do poço
                  </button>
                </div>
              )}
              <p className="chart-caption">
                A base é transversal, sem datas para criar uma série temporal.
              </p>
            </article>
          </section>
        </>
      )}

      <WellInputDialog dialogRef={dialogRef} onPrediction={setPrediction} />
    </div>
  )
}

export default DashboardPage
