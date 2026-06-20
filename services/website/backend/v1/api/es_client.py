from elasticsearch import Elasticsearch, exceptions as es_exceptions
from django.conf import settings

def get_es_client():
    try:
        es = Elasticsearch(
            hosts=[f"http://{settings.ELASTICSEARCH_HOST}:{settings.ELASTICSEARCH_PORT}"],
            basic_auth=(settings.ELASTICSEARCH_USER, settings.ELASTICSEARCH_PASSWORD),
            verify_certs=False,
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