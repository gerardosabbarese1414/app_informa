# InForma - struttura modulare

Questa versione spezza il vecchio `pages.py` in moduli piccoli.

## Entry point
- `app.py`

## Router
- `router.py` (seleziona e renderizza la pagina richiesta)

## Pagine
- `views/calendar_month.py`
- `views/day.py`
- `views/dashboard.py`
- `views/weekly_plan.py`

## Componenti (sezioni)
- `components/planned_section.py`
- `components/actual_section.py`
- `components/meal_forms.py`
- `components/workout_forms.py`

Ogni sezione è protetta da `components/safe.py`:
se una sezione va in errore, la pagina resta disponibile e mostra l'errore solo per quella parte.

## DB repositories
- `db/repo_*.py` per isolare l’accesso SQL.

## AI
- `services/ai_service.py` (wrapper OpenAI con retry + note di fallback)
- `ai.py` re-export per compatibilità.
