# Minion WebUI

A Flask-based WebUI for monitoring and controlling Agent Zero minion agents.

## Setup

1. Copy `.env.example` to `.env` and set your secrets.
2. Run database migrations: `flask db init && flask db migrate -m "initial" && flask db upgrade`
3. Start the application: `docker-compose up --build`

Visit http://localhost:5000 to access the WebUI.
