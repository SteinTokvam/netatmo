# Copilot instructions for `netatmo`

## Build, run, and validation commands

```bash
python3 -m pip install -r requirements.txt
python3 server.py
python3 display.py
python3 weather.py
docker build -t ghcr.io/steintokvam/netatmo:latest .
```

There is no checked-in automated test suite, lint configuration, `Makefile`, `pyproject.toml`, or `pytest`/`unittest` test directory in this repository. A single-test command is therefore not applicable here.

Use `python3 server.py` as the main runtime entry point. The README still describes running `netatmo.py` directly, but the current codebase does not expose a script entry point there; `netatmo.py` is started by `server.py` in a background thread.

## High-level architecture

`server.py` is the composition root. It reads `config/config.json`, starts three daemon threads, serves aggregated JSON on `http://0.0.0.0:8000/data.json`, and exposes a lightweight liveness endpoint on `http://0.0.0.0:8000/healthz`.

- `netatmo.startNetatmoService(config)` polls the Netatmo API, refreshes OAuth tokens in `config/token.json`, writes station data to `data/data.json`, logs a compact console summary, and triggers `display.main()` after each successful cycle.
- `weather.startWeatherService()` polls the met.no forecast API hourly and writes `data/weather_data.json`.
- `ical_calendar.calendar_service(config)` polls a CalDAV calendar (currently expected to be iCloud-compatible credentials in `config/config.json`) and writes `data/events.json`.
- `WeatherHandler` in `server.py` is a read-model layer: it does not call upstream APIs directly. It reads the JSON files produced by the background services and reshapes them into a smaller `/data.json` payload containing `yr`, `netatmo`, and `events`.

The repository is organized around a file-based data pipeline. Producers write JSON into `data/`, and consumers read those files later. `display.py` follows that pattern too: it reads `data/data.json` and `data/weather_data.json`, combines live station data with forecast icons from `symbols/`, and renders `image.bmp`.

`2-7-inch-display.py` is an older hardware-focused renderer for PaPiRus/Waveshare devices. The actively used renderer in the current flow is `display.py`, which produces a 960x540 bitmap and does not get imported by `server.py` through the legacy hardware script.

The Docker image and the GitHub Actions workflow both treat `server.py` as the application entry point.

## Key conventions

- Keep configuration under `config/` and generated runtime artifacts under `data/`. The current code expects:
  - `config/config.json` for Netatmo and CalDAV credentials/settings
  - `config/token.json` for Netatmo OAuth tokens
  - `data/data.json`, `data/weather_data.json`, and `data/events.json` as service outputs
- Preserve the file contracts between modules. `server.py` and `display.py` assume the Netatmo and met.no payloads keep their current nested JSON shapes; changes to producer structure usually require coordinated changes in consumers.
- Treat service modules as long-running loops, not CLI utilities. `netatmo.py`, `weather.py`, and `ical_calendar.py` are primarily imported and launched by `server.py`.
- `display.py` depends on local assets being present relative to the repository root: `free-sans.ttf`, `symbols/*.png`, and the JSON files in `data/`. If you move paths or add new renderers, keep those relative-path assumptions in mind.
- Netatmo module handling is keyed off Netatmo type IDs, not custom abstractions:
  - `NAModule1` = outdoor module
  - `NAModule2` = wind gauge
  - `NAModule3` = rain gauge
  - `NAModule4` = optional indoor module
- Forecast location is hard-coded in `weather.py` (`altitude`, `lat`, `lon`). If location should become configurable, wire it through `config/config.json` and update all callers consistently.
- The server exposes `/data.json` for aggregated data and `/healthz` for liveness checks. Keep `/data.json` stable for existing consumers, and use `/healthz` for lightweight Docker/Kubernetes health probes instead of the heavier aggregation endpoint.
