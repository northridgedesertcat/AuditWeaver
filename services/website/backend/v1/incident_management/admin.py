from django.contrib import admin

from .models import Incident, IncidentTimeline


class IncidentTimelineInline(admin.TabularInline):
    model = IncidentTimeline
    extra = 0
    fields = ('action', 'content', 'operator', 'created_at')
    readonly_fields = ('created_at',)
    ordering = ('created_at',)


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'title', 'severity', 'status',
        'assignee', 'created_by', 'created_at',
    )
    list_filter = ('status', 'severity', 'created_at')
    search_fields = ('id', 'external_event_id', 'title', 'source_ip')
    readonly_fields = ('created_at', 'updated_at', 'version')
    inlines = [IncidentTimelineInline]


@admin.register(IncidentTimeline)
class IncidentTimelineAdmin(admin.ModelAdmin):
    list_display = ('id', 'incident', 'action', 'operator', 'created_at')
    list_filter = ('action', 'created_at')
    search_fields = ('incident__id', 'incident__title', 'content')
    readonly_fields = ('created_at',)
