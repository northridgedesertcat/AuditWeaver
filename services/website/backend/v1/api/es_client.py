from elasticsearch import Elasticsearch, exceptions as es_exceptions
from django.conf import settings

def get_es_client():
    try:
        scheme = "https" if settings.ELASTICSEARCH_USE_SSL else "http"
        es = Elasticsearch(
            hosts=[f"{scheme}://{settings.ELASTICSEARCH_HOST}:{settings.ELASTICSEARCH_PORT}"],
            basic_auth=(settings.ELASTICSEARCH_USER, settings.ELASTICSEARCH_PASSWORD),
            verify_certs=settings.ELASTICSEARCH_VERIFY_CERTS,
            ssl_show_warn=False,
        )
        return es
    except Exception:
        return None

def is_es_available():
    es = get_es_client()
    if es is None:
        return False
    try:
        return es.ping()
    except:
        return False