"""
Management command: python manage.py export_registrations

Exports all completed registrations to a CSV file.
Columns are dynamic — built from the active Question field_names.

Usage:
  python manage.py export_registrations
  python manage.py export_registrations --output /tmp/registrations.csv
"""
import csv
import os
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Export all completed registrations to a CSV file'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            default=None,
            help='Output CSV file path (default: registrations_YYYYMMDD.csv)',
        )

    def handle(self, *args, **options):
        from apps.registration.models import Question, RegistrationSession

        # Build ordered column list from active questions
        questions = list(Question.objects.filter(is_active=True).order_by('order'))
        field_names = [q.field_name for q in questions]
        q_labels = {q.field_name: q.text[:40] for q in questions}

        # Completed sessions only
        sessions = (
            RegistrationSession.objects
            .filter(is_completed=True)
            .select_related('user')
            .order_by('completed_at')
        )

        if not sessions.exists():
            self.stdout.write(self.style.WARNING('No completed registrations found.'))
            return

        # Output path
        output = options['output'] or f'registrations_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv'

        with open(output, 'w', newline='', encoding='utf-8-sig') as csvfile:
            # Header: meta fields + question fields
            meta_fields = ['bale_user_id', 'username', 'full_name', 'registered_at']
            writer = csv.DictWriter(
                csvfile,
                fieldnames=meta_fields + field_names,
                extrasaction='ignore',
            )

            # Write header row with human-readable labels
            header = {
                'bale_user_id': 'شناسه بله',
                'username': 'نام کاربری',
                'full_name': 'نام کامل',
                'registered_at': 'زمان ثبت‌نام',
            }
            header.update(q_labels)
            writer.writerow(header)

            # Write data rows
            count = 0
            for session in sessions:
                row = {
                    'bale_user_id': session.user.bale_user_id,
                    'username': session.user.username,
                    'full_name': session.user.full_name,
                    'registered_at': (
                        session.completed_at.strftime('%Y-%m-%d %H:%M:%S')
                        if session.completed_at else ''
                    ),
                }
                row.update(session.answers or {})
                writer.writerow(row)
                count += 1

        self.stdout.write(self.style.SUCCESS(
            f'✅ Exported {count} registrations to: {os.path.abspath(output)}'
        ))
