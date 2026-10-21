I set up an nginx reverse proxy in front of two Flask microservices — a weather service and an alerts service — but every request through nginx returns a 404. The Flask services themselves work fine on their own ports.

The setup:
- Weather service runs on 127.0.0.1:5001 with endpoints /forecast and /conditions
- Alerts service runs on 127.0.0.1:5002 with endpoints /active and /history
- Nginx on port 80 should proxy /weather/* to the weather service and /alerts/* to the alerts service
- All processes are managed by supervisord

The nginx config is at /etc/nginx/sites-available/default. The Flask source files are in /app. After fixing the config, reload or restart nginx so changes take effect.

What should work after the fix — all via http://localhost:

- GET /weather/forecast → JSON: {"service":"weather","endpoint":"forecast","temp_c":22,"condition":"sunny"}
- GET /weather/conditions → JSON: {"service":"weather","endpoint":"conditions","humidity_pct":45,"wind_kph":12}
- GET /alerts/active → JSON: {"service":"alerts","endpoint":"active","count":3,"highest_severity":"warning"}
- GET /alerts/history → JSON: {"service":"alerts","endpoint":"history","total":47,"last_date":"2024-11-15"}

Each must return HTTP 200 with the exact JSON shown. Please fix the proxy configuration so all four endpoints respond correctly.
