from django.db import models


class Checkpoint(models.Model):
    sink = models.CharField(max_length=16)
    topic = models.CharField(max_length=128)
    partition = models.IntegerField()
    next_offset = models.BigIntegerField(default=0)
    initial_offset = models.BigIntegerField(default=0)
    observed_next_offset = models.BigIntegerField(default=0)
    generation = models.CharField(max_length=64, default="v1")
    partition_count = models.IntegerField(default=0)
    checked_at = models.DateTimeField(null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "log_storage_checkpoint"
        constraints = [models.UniqueConstraint(fields=["sink", "topic", "partition"], name="storage_checkpoint_source")]


class Gap(models.Model):
    sink = models.CharField(max_length=16)
    topic = models.CharField(max_length=128)
    partition = models.IntegerField()
    offset = models.BigIntegerField()
    error = models.TextField()
    resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "log_storage_gap"
        constraints = [models.UniqueConstraint(fields=["sink", "topic", "partition", "offset"], name="storage_gap_source")]


class ArchiveManifest(models.Model):
    index_name = models.CharField(max_length=255, unique=True)
    kind = models.CharField(max_length=8)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    state = models.CharField(max_length=32, default="OPEN")
    source_bounds = models.JSONField(default=dict)
    record_count = models.BigIntegerField(default=0)
    digest = models.CharField(max_length=64, blank=True)
    backup_id = models.CharField(max_length=255, blank=True)
    evidence = models.JSONField(default=dict)
    error = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "log_archive_manifest"


class CoverageWindow(models.Model):
    kind = models.CharField(max_length=16)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    evidence = models.JSONField(default=dict)
    verified = models.BooleanField(default=False)

    class Meta:
        db_table = "log_storage_coverage"


class EventOutbox(models.Model):
    topic = models.CharField(max_length=128)
    partition = models.IntegerField()
    offset = models.BigIntegerField()
    event_id = models.CharField(max_length=255)
    event_time = models.DateTimeField()
    processed_at = models.DateTimeField(null=True, db_index=True)

    class Meta:
        db_table = "log_storage_event_outbox"
        constraints = [models.UniqueConstraint(fields=["topic", "partition", "offset"], name="storage_outbox_source")]
