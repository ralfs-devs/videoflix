#!/bin/sh

set -e

echo "Waiting for PostgreSQL on $DB_HOST:$DB_PORT..."

while ! pg_isready -h "$DB_HOST" -p "$DB_PORT" -q; do
  echo "Could not reach PostgreSQL - sleeping for 1 second"
  sleep 1
done

echo "PostgreSQL ready - continuing..."

python manage.py collectstatic --noinput

if [ "${SKIP_MIGRATIONS:-false}" != "true" ]; then
    echo "Running migrations..."
    python manage.py makemigrations
    python manage.py migrate

    python manage.py shell <<EOF
import os
from django.contrib.auth import get_user_model

User = get_user_model()
username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@example.com')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'adminpassword')

if not User.objects.filter(username=username).exists():
    print(f"Creating superuser '{username}'...")
    User.objects.create_superuser(username=username, email=email, password=password)
    print(f"Superuser '{username}' created.")
else:
    print(f"Updating password for superuser '{username}'...")
    user = User.objects.get(username=username)
    user.set_password(password)
    user.email = email
    user.save()
    print(f"Superuser '{username}' password updated.")
EOF
else
    echo "Skipping migrations and superuser creation (SKIP_MIGRATIONS=true)"
fi

python manage.py rqworker default &

exec gunicorn core.wsgi:application --bind 0.0.0.0:8000 --reload --access-logfile - --log-level info