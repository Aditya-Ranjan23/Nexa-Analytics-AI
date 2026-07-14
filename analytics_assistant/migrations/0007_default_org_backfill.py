"""
Data migration: create the default Organization and backfill all existing
DatasetUpload, ChatSession, and DashboardState rows that have no org yet.

This ensures the system stays coherent after the schema migration adds the
nullable organization FK. All pre-org data is grouped under 'Default Organization'.
"""

from django.db import migrations


def create_default_org_and_backfill(apps, schema_editor):
    Organization = apps.get_model("analytics_assistant", "Organization")
    DatasetUpload = apps.get_model("analytics_assistant", "DatasetUpload")
    ChatSession = apps.get_model("analytics_assistant", "ChatSession")
    DashboardState = apps.get_model("analytics_assistant", "DashboardState")

    default_org, _ = Organization.objects.get_or_create(
        slug="default",
        defaults={"name": "Default Organization"},
    )

    DatasetUpload.objects.filter(organization__isnull=True).update(organization=default_org)
    ChatSession.objects.filter(organization__isnull=True).update(organization=default_org)
    DashboardState.objects.filter(organization__isnull=True).update(organization=default_org)


def reverse_backfill(apps, schema_editor):
    # Reversing simply clears the backfilled org — the schema migration handles
    # removing the column if the previous migration is also reversed.
    Organization = apps.get_model("analytics_assistant", "Organization")
    DatasetUpload = apps.get_model("analytics_assistant", "DatasetUpload")
    ChatSession = apps.get_model("analytics_assistant", "ChatSession")
    DashboardState = apps.get_model("analytics_assistant", "DashboardState")

    try:
        default_org = Organization.objects.get(slug="default")
        DatasetUpload.objects.filter(organization=default_org).update(organization=None)
        ChatSession.objects.filter(organization=default_org).update(organization=None)
        DashboardState.objects.filter(organization=default_org).update(organization=None)
        default_org.delete()
    except Organization.DoesNotExist:
        pass


class Migration(migrations.Migration):

    dependencies = [
        ("analytics_assistant", "0006_org_model_and_dataset_fields"),
    ]

    operations = [
        migrations.RunPython(
            create_default_org_and_backfill,
            reverse_code=reverse_backfill,
        ),
    ]
