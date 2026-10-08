web: python manage.py migrate && gunicorn expense_tracker_project.wsgi:application --bind 0.0.0.0:${PORT:-8000}
