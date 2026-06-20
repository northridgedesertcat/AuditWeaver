from rest_framework import serializers

class AlertSerializer(serializers.Serializer):
    id = serializers.CharField()
    title = serializers.CharField()
    description = serializers.CharField()
    severity = serializers.CharField()
    status = serializers.CharField()
    source = serializers.CharField()
    timestamp = serializers.CharField()
    count = serializers.IntegerField()

class AlertRuleSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    enabled = serializers.BooleanField()
    severity = serializers.CharField()
    notifications = serializers.BooleanField()

class IncidentSerializer(serializers.Serializer):
    id = serializers.CharField()
    title = serializers.CharField()
    description = serializers.CharField()
    severity = serializers.CharField()
    status = serializers.CharField()
    assignee = serializers.CharField(allow_null=True)
    createdAt = serializers.CharField()
    updatedAt = serializers.CharField()
    progress = serializers.IntegerField()
    affectedSystems = serializers.ListField(child=serializers.CharField())
    timeline = serializers.ListField(child=serializers.DictField())

class AnomalySerializer(serializers.Serializer):
    id = serializers.CharField()
    type = serializers.CharField()
    title = serializers.CharField()
    description = serializers.CharField()
    severity = serializers.CharField()
    score = serializers.IntegerField()
    timestamp = serializers.CharField()
    source = serializers.CharField()
    details = serializers.DictField()
    status = serializers.CharField()

class ServerSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    type = serializers.CharField()
    status = serializers.CharField()
    cpu = serializers.IntegerField()
    memory = serializers.IntegerField()
    disk = serializers.IntegerField()
    network = serializers.CharField()
    uptime = serializers.CharField()
    location = serializers.CharField()

class ThreatSerializer(serializers.Serializer):
    id = serializers.CharField()
    indicator = serializers.CharField()
    type = serializers.CharField()
    category = serializers.CharField()
    severity = serializers.CharField()
    source = serializers.CharField()
    firstSeen = serializers.CharField()
    lastSeen = serializers.CharField()
    country = serializers.CharField()
    tags = serializers.ListField(child=serializers.CharField())

class AIModelSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    type = serializers.CharField()
    status = serializers.CharField()
    accuracy = serializers.FloatField()
    latency = serializers.CharField()
    lastTrained = serializers.CharField()
    tasksProcessed = serializers.IntegerField()

class DashboardStatsSerializer(serializers.Serializer):
    logVolume = serializers.CharField()
    attackLogs = serializers.IntegerField()
    highSeverityAlerts = serializers.IntegerField()
    riskIps = serializers.IntegerField()
    totalLogs = serializers.IntegerField()
    avgResponseTime = serializers.CharField()