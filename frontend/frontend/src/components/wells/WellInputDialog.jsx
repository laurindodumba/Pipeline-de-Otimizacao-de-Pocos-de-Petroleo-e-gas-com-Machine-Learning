import { useState } from 'react'
import { predictDailyMargin } from '../../services/apiClient.js'
import './WellInputDialog.css'

const fields = [
  { name: 'permeability_md', label: 'Permeabilidade', unit: 'mD', min: '0' },
  { name: 'porosity_fraction', label: 'Porosidade', unit: 'fração (0–1)', min: '0', max: '1' },
  { name: 'well_depth_ft', label: 'Profundidade do poço', unit: 'ft', min: '0.000001' },
  { name: 'tubing_diameter_in', label: 'Diâmetro do tubing', unit: 'in', min: '0.000001' },
  { name: 'choke_size_64th', label: 'Abertura do choke', unit: '64 avos', min: '0.000001' },
  { name: 'reservoir_pressure_psi', label: 'Pressão do reservatório', unit: 'psi', min: '0' },
  { name: 'reservoir_temp_f', label: 'Temperatura do reservatório', unit: '°F', min: '-459.66' },
  { name: 'oil_gravity_api', label: 'Grau API do óleo', unit: '°API', min: '0.000001' },
  { name: 'gas_oil_ratio_scf_bbl', label: 'Razão gás/óleo', unit: 'scf/bbl', min: '0' },
  { name: 'bottomhole_pressure_psi', label: 'Pressão de fundo', unit: 'psi', min: '0' },
  { name: 'wellhead_pressure_psi', label: 'Pressão na cabeça do poço', unit: 'psi', min: '0' },
  { name: 'water_cut_fraction', label: 'Corte de água', unit: 'fração (0–1)', min: '0', max: '1' },
  { name: 'oil_price_usd_bbl', label: 'Preço do petróleo', unit: 'USD/bbl', min: '0' },
  { name: 'gas_price_usd_mcf', label: 'Preço do gás', unit: 'USD/Mcf', min: '0' },
]

const initialValues = Object.fromEntries(fields.map(({ name }) => [name, '']))

function WellInputDialog({ dialogRef, onPrediction }) {
  const [values, setValues] = useState(initialValues)
  const [errorMessage, setErrorMessage] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  function updateField(event) {
    const { name, value } = event.target
    setValues((currentValues) => ({ ...currentValues, [name]: value }))
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setErrorMessage('')
    setIsSubmitting(true)

    try {
      const input = Object.fromEntries(
        Object.entries(values).map(([name, value]) => [name, Number(value)]),
      )
      const result = await predictDailyMargin(input)
      onPrediction(result)
      dialogRef.current?.close()
    } catch (error) {
      setErrorMessage(error.message || 'Falha ao comunicar com a API.')
    } finally {
      setIsSubmitting(false)
    }
  }

  function closeDialog() {
    if (!isSubmitting) {
      dialogRef.current?.close()
    }
  }

  return (
    <dialog
      className="estimate-dialog"
      ref={dialogRef}
      aria-labelledby="estimate-dialog-title"
    >
      <div className="estimate-dialog__header">
        <div>
          <p className="eyebrow">NOVA ESTIMATIVA</p>
          <h2 id="estimate-dialog-title">Condições observadas do poço</h2>
        </div>
        <button
          className="dialog-close"
          type="button"
          onClick={closeDialog}
          aria-label="Fechar formulário"
          disabled={isSubmitting}
        >
          ×
        </button>
      </div>

      <form className="well-form" onSubmit={handleSubmit}>
        <div className="well-form__grid">
          {fields.map(({ name, label, unit, min, max }) => (
            <label className="field" htmlFor={name} key={name}>
              <span className="field__label">{label}</span>
              <span className="field__control">
                <input
                  id={name}
                  name={name}
                  type="number"
                  inputMode="decimal"
                  min={min}
                  max={max}
                  step="any"
                  value={values[name]}
                  onChange={updateField}
                  required
                />
                <span className="field__unit">{unit}</span>
              </span>
            </label>
          ))}
        </div>

        {errorMessage && (
          <p className="form-message" role="alert">
            {errorMessage}
          </p>
        )}

        <div className="well-form__footer">
          <p>Valores de porosidade e corte de água devem estar entre 0 e 1.</p>
          <div className="well-form__actions">
            <button
              className="secondary-button"
              type="button"
              onClick={closeDialog}
              disabled={isSubmitting}
            >
              Cancelar
            </button>
            <button className="primary-button" type="submit" disabled={isSubmitting}>
              {isSubmitting ? 'Calculando…' : 'Calcular margem'}
            </button>
          </div>
        </div>
      </form>
    </dialog>
  )
}

export default WellInputDialog
