# cmu_lhs_pm_project

## DustBoy live environmental data

The dashboard requests fresh DustBoy station data when a page opens. Filter changes reuse the recent server response for five minutes. The API key stays on the FastAPI server. The patient data still comes from `patients.csv`.

For local development, add `DUST_BOY_API_KEY=your-key` to an untracked `.env` file, install `requirements.txt`, and run `uvicorn main:app --reload`. On Render, keep `DUST_BOY_API_KEY` in the service environment variables. Set `DUST_BOY_CACHE_PATH` to a path on a [Render persistent disk](https://render.com/docs/disks) if the last successful readings must survive service restarts or redeploys; otherwise the default `cache/dustboy.sqlite3` lasts only as long as the instance's filesystem.

Each successful response saves the current station readings. The chart builds a trend from those saved observations, up to 30 days. When exactly one station is selected, the server also attempts the DustBoy 30-day history endpoint at most once per hour across the site; this method has a separate API quota. If DustBoy fails, the server uses the latest saved response and labels the page as cached. Before the first successful response, an API failure is shown as unavailable.
