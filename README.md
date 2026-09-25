# cmu_lhs_pm_project

## DustBoy live environmental data

The dashboard requests fresh DustBoy station and 30-day observation data when it opens and when a filter changes. The API key stays on the FastAPI server. The patient data still comes from `patients.csv`.

For local development, add `DUST_BOY_API_KEY=your-key` to an untracked `.env` file, install `requirements.txt`, and run `uvicorn main:app --reload`. On Render, keep `DUST_BOY_API_KEY` in the service environment variables. Set `DUST_BOY_CACHE_PATH` to a path on a [Render persistent disk](https://render.com/docs/disks) if the last successful readings must survive service restarts or redeploys; otherwise the default `cache/dustboy.sqlite3` lasts only as long as the instance's filesystem.

The dashboard supports the most recent 30 days because that is the range provided by the DustBoy station history endpoint. Each successful response replaces the saved readings for that station. If DustBoy fails, the server uses the latest saved response and labels the page as cached. Before the first successful response, an API failure is shown as unavailable.
